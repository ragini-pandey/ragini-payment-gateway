"""Fan a webhook_events row out to matching webhooks → per-delivery dispatch."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.webhook import Webhook
from app.models.webhook_delivery import WebhookDelivery
from app.models.webhook_event import WebhookEvent
from app.workers._async import run_async
from app.workers.celery_app import celery_app


async def _fanout(event_id: uuid.UUID) -> int:
    async with AsyncSessionLocal() as db:
        event = (
            await db.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
        ).scalar_one_or_none()
        if event is None:
            return 0

        # Find every active webhook in the same (user, environment) subscribed
        # to this event_type.
        webhooks = list(
            (
                await db.execute(
                    select(Webhook).where(
                        Webhook.user_id == event.user_id,
                        Webhook.environment == event.environment,
                        Webhook.status == "active",
                        Webhook.events.any(event.event_type),  # postgres ARRAY containment
                    )
                )
            )
            .scalars()
            .all()
        )

        delivery_ids: list[uuid.UUID] = []
        for wh in webhooks:
            row = WebhookDelivery(
                webhook_id=wh.id,
                user_id=event.user_id,
                environment=event.environment,
                event_id=event.id,
                event_type=event.event_type,
                status="pending",
                attempt=1,
            )
            db.add(row)
            await db.flush()
            delivery_ids.append(row.id)
        await db.commit()

    from app.workers.tasks.dispatch_delivery import dispatch_delivery

    for did in delivery_ids:
        dispatch_delivery.delay(str(did))
    return len(delivery_ids)


@celery_app.task(name="app.workers.tasks.fanout_event.fanout_event")
def fanout_event(event_id: str) -> int:
    return run_async(_fanout(uuid.UUID(event_id)))
