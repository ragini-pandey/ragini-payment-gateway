"""Event emitter — the single funnel for every emitted webhook event.

Flow:
1. ``emit(...)`` inserts a row into ``webhook_events`` (transactional outbox-lite).
2. Enqueues a Celery ``fanout_event`` task with the event id.
3. The worker creates one ``webhook_deliveries`` row per subscribed webhook
   and enqueues a ``dispatch_delivery`` task for each.

Why a DB row + task (vs. direct fanout): if the worker is down, events are
preserved and can be replayed; the work boundary is moved off the request hot
path.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import EventType
from app.models.security_alert import SecurityAlert
from app.models.webhook_event import WebhookEvent


async def emit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    environment: str,
    event_type: EventType | str,
    data: dict[str, Any],
) -> uuid.UUID:
    """Persist the event and enqueue fan-out. Returns the event id.

    The caller is responsible for committing the surrounding transaction.
    """
    et = event_type.value if isinstance(event_type, EventType) else event_type
    result = await db.execute(
        insert(WebhookEvent)
        .values(
            user_id=user_id,
            environment=environment,
            event_type=et,
            payload=data,
        )
        .returning(WebhookEvent.id)
    )
    event_id = result.scalar_one()

    # Enqueue fan-out AFTER commit using a small trick: SQLAlchemy "after_commit"
    # hooks would be ideal; here we lean on the route/service to commit and
    # call ``schedule_fanout`` itself. We expose it as a helper to keep this
    # module import-light (no celery_app import → avoids circular imports in
    # places that only need to write the event row, e.g. tests).
    return event_id


def schedule_fanout(event_id: uuid.UUID) -> None:
    """Enqueue the Celery fan-out task. Safe to call after commit."""
    # Local import to avoid pulling Celery into every code path.
    from app.workers.tasks.fanout_event import fanout_event

    fanout_event.delay(str(event_id))


async def emit_security_alert(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    environment: str,
    alert_type: str,
    severity: str = "low",
    api_key_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Insert a ``security_alerts`` row AND emit a ``security.alert`` event.

    Returns the event id (so the caller can schedule fan-out post-commit).
    """
    details = details or {}
    await db.execute(
        insert(SecurityAlert).values(
            user_id=user_id,
            environment=environment,
            api_key_id=api_key_id,
            alert_type=alert_type,
            severity=severity,
            details=details,
        )
    )
    return await emit(
        db,
        user_id=user_id,
        environment=environment,
        event_type=EventType.SECURITY_ALERT,
        data={"alert_type": alert_type, "severity": severity, **details},
    )
