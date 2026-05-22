"""Sign + POST a webhook delivery; record response; schedule retry on failure.

Backoff schedule (seconds): 60, 300, 1800, 7200, 43200, 86400 — i.e.
1 min, 5 min, 30 min, 2 h, 12 h, 24 h. Each attempt is its own
``webhook_deliveries`` row so the dashboard shows the full attempt history.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models.webhook import Webhook
from app.models.webhook_delivery import WebhookDelivery
from app.models.webhook_event import WebhookEvent
from app.security.hmac_sign import sign
from app.services import event_emitter
from app.workers._async import run_async
from app.workers.celery_app import celery_app

BACKOFF_SECONDS: tuple[int, ...] = (60, 300, 1800, 7200, 43200, 86400)


def _backoff_with_jitter(attempt: int) -> int:
    """attempt is 1-indexed; returns delay for the *next* attempt."""
    idx = max(0, min(attempt - 1, len(BACKOFF_SECONDS) - 1))
    base = BACKOFF_SECONDS[idx]
    jitter = random.uniform(-0.15, 0.15) * base
    return max(1, int(base + jitter))


async def _dispatch(delivery_id: uuid.UUID) -> str:
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        delivery = (
            await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
        ).scalar_one_or_none()
        if delivery is None or delivery.status not in ("pending", "retrying"):
            return "skipped"

        webhook = (
            await db.execute(select(Webhook).where(Webhook.id == delivery.webhook_id))
        ).scalar_one_or_none()
        if webhook is None:
            delivery.status = "failed"
            delivery.response_body = "webhook deleted"
            await db.commit()
            return "webhook_missing"

        event_payload: dict = {}
        event_created: datetime | None = None
        if delivery.event_id is not None:
            ev = (
                await db.execute(select(WebhookEvent).where(WebhookEvent.id == delivery.event_id))
            ).scalar_one_or_none()
            if ev is not None:
                event_payload = ev.payload
                event_created = ev.created_at

        body_obj = {
            "id": str(delivery.event_id or delivery.id),
            "type": delivery.event_type,
            "created": int((event_created or datetime.now(timezone.utc)).timestamp()),
            "environment": delivery.environment,
            "data": event_payload,
        }
        body = json.dumps(body_obj, separators=(",", ":"), default=str).encode("utf-8")
        signed = sign(webhook.secret, body)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Ragini-Webhooks/1.0",
            "X-Ragini-Signature": signed.signature_header,
            "X-Ragini-Event": delivery.event_type,
            "X-Ragini-Delivery": str(delivery.id),
        }

        status_code: int | None = None
        response_text: str | None = None
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_http_timeout_seconds) as client:
                resp = await client.post(str(webhook.url), content=body, headers=headers)
                status_code = resp.status_code
                response_text = resp.text[:4096]
        except httpx.HTTPError as e:
            response_text = f"transport_error: {e}"[:4096]

        succeeded = status_code is not None and 200 <= status_code < 300
        delivery.response_code = status_code
        delivery.response_body = response_text

        if succeeded:
            delivery.status = "success"
            await db.commit()
            return "success"

        if delivery.attempt >= settings.webhook_max_attempts:
            delivery.status = "dead_lettered"
            event_id = await event_emitter.emit_security_alert(
                db,
                user_id=delivery.user_id,
                environment=delivery.environment,
                alert_type="webhook_dead_lettered",
                severity="low",
                details={
                    "webhook_id": str(delivery.webhook_id),
                    "delivery_id": str(delivery.id),
                    "attempts": delivery.attempt,
                    "last_status": status_code,
                },
            )
            await db.commit()
            event_emitter.schedule_fanout(event_id)
            return "dead_lettered"

        # Schedule a new attempt as a NEW delivery row (preserves history).
        delivery.status = "failed"
        next_attempt = delivery.attempt + 1
        delay = _backoff_with_jitter(delivery.attempt)
        eta = datetime.now(timezone.utc) + timedelta(seconds=delay)
        retry_row = WebhookDelivery(
            webhook_id=delivery.webhook_id,
            user_id=delivery.user_id,
            environment=delivery.environment,
            event_id=delivery.event_id,
            event_type=delivery.event_type,
            status="retrying",
            attempt=next_attempt,
            next_attempt_at=eta,
        )
        db.add(retry_row)
        await db.flush()
        retry_id = retry_row.id
        await db.commit()

    dispatch_delivery.apply_async(args=[str(retry_id)], eta=eta)
    return "retry_scheduled"


@celery_app.task(name="app.workers.tasks.dispatch_delivery.dispatch_delivery")
def dispatch_delivery(delivery_id: str) -> str:
    return run_async(_dispatch(uuid.UUID(delivery_id)))
