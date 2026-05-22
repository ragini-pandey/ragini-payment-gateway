"""Delivery retry endpoint (dashboard)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.deps import CurrentUser, DbDep
from app.models.webhook_delivery import WebhookDelivery
from app.services import audit

router = APIRouter(prefix="/v1/deliveries", tags=["deliveries"])


@router.post("/{delivery_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_delivery(
    delivery_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> dict:
    delivery = (
        await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.id == delivery_id,
                WebhookDelivery.user_id == user.user_id,
            )
        )
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery not found")

    retry = WebhookDelivery(
        webhook_id=delivery.webhook_id,
        user_id=delivery.user_id,
        environment=delivery.environment,
        event_id=delivery.event_id,
        event_type=delivery.event_type,
        status="pending",
        attempt=delivery.attempt + 1,
    )
    db.add(retry)
    await db.flush()
    retry_id = retry.id
    await audit.record(
        db,
        request=request,
        actor_user_id=user.user_id,
        action="webhook_delivery.manual_retry",
        target_type="webhook_delivery",
        target_id=delivery.id,
        environment=delivery.environment,
        metadata={"retryDeliveryId": str(retry_id), "attempt": retry.attempt},
    )
    await db.commit()

    from app.workers.tasks.dispatch_delivery import dispatch_delivery

    dispatch_delivery.delay(str(retry_id))
    return {"deliveryId": str(retry_id), "queued": True}
