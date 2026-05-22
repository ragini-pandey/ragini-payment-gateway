"""Demo public API — exercises the API-key auth path and emits payment events.

This endpoint does NOT process real payments. It exists so the whole pipeline
(API key verification → event emission → webhook signing → async delivery →
retry) can be demonstrated end-to-end with ``curl``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, status
from typing import Annotated

from app.deps import CurrentApiKey, DbDep
from app.events import EventType
from app.redis_client import get_redis
from app.schemas import CamelModel
from app.services import event_emitter

router = APIRouter(prefix="/v1/payments", tags=["payments"])


class CreatePaymentRequest(CamelModel):
    amount: int  # in minor units (e.g. cents)
    currency: str = "USD"
    customer_id: str | None = None
    fail: bool = False


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: CreatePaymentRequest,
    api_key: CurrentApiKey,
    db: DbDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    if payload.amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "amount must be positive")

    # Idempotency: 24h dedupe per (key_id, idempotency_key).
    if idempotency_key:
        redis = get_redis()
        cache_key = f"idem:{api_key.key_id}:{idempotency_key}"
        cached = await redis.get(cache_key)
        if cached is not None:
            return {"paymentId": cached, "status": "idempotent_replay"}

    payment_id = f"pay_{uuid.uuid4().hex[:24]}"
    if payload.fail:
        event_id = await event_emitter.emit(
            db,
            user_id=api_key.user_id,
            environment=api_key.environment,
            event_type=EventType.PAYMENT_ERROR,
            data={
                "payment_id": payment_id,
                "amount": payload.amount,
                "currency": payload.currency,
                "customer_id": payload.customer_id,
                "error": "card_declined",
            },
        )
        await db.commit()
        event_emitter.schedule_fanout(event_id)
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Payment declined")

    event_id = await event_emitter.emit(
        db,
        user_id=api_key.user_id,
        environment=api_key.environment,
        event_type=EventType.PAYMENT_SUCCESS,
        data={
            "payment_id": payment_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "customer_id": payload.customer_id,
        },
    )
    await db.commit()
    event_emitter.schedule_fanout(event_id)

    if idempotency_key:
        await get_redis().set(
            f"idem:{api_key.key_id}:{idempotency_key}", payment_id, ex=24 * 3600
        )
    return {"paymentId": payment_id, "status": "succeeded"}
