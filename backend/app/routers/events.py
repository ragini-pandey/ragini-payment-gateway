"""Generic event ingestion endpoint (public API, API-key auth).

Lets external systems (or our own dashboard test button) emit any event from
the canonical catalog. Each accepted call writes a row to ``webhook_events``
and enqueues a Celery ``fanout_event`` task. Optional ``Idempotency-Key``
header dedupes within 24 h per (key_id, idempotency_key).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, status

from app.deps import CurrentApiKey, DbDep
from app.events import EventType, is_valid_event_type
from app.redis_client import get_redis
from app.schemas import CamelModel
from app.services import event_emitter

router = APIRouter(prefix="/v1/events", tags=["events"])


class IngestEventRequest(CamelModel):
    event_type: str
    data: dict[str, Any] = {}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    payload: IngestEventRequest,
    api_key: CurrentApiKey,
    db: DbDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    if not is_valid_event_type(payload.event_type):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown event type: {payload.event_type}",
        )

    if idempotency_key:
        redis = get_redis()
        cache_key = f"idem:event:{api_key.key_id}:{idempotency_key}"
        cached = await redis.get(cache_key)
        if cached is not None:
            return {"eventId": cached, "status": "idempotent_replay"}

    event_id = await event_emitter.emit(
        db,
        user_id=api_key.user_id,
        environment=api_key.environment,
        event_type=EventType(payload.event_type),
        data=payload.data,
    )
    await db.commit()
    event_emitter.schedule_fanout(event_id)

    if idempotency_key:
        await get_redis().set(
            f"idem:event:{api_key.key_id}:{idempotency_key}",
            str(event_id),
            ex=24 * 3600,
        )

    return {"eventId": str(event_id), "queued": True}
