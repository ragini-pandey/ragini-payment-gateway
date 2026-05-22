"""Webhook management routes (dashboard, Supabase JWT auth)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.deps import CurrentUser, DbDep, EnvironmentDep
from app.events import EventType, is_valid_event_type
from app.schemas.webhook import (
    CreateWebhookRequest,
    DeliveryListResponse,
    UpdateWebhookRequest,
    Webhook,
)
from app.services import audit, event_emitter, webhook_service

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


class TestEventBody(BaseModel):
    event_type: str = EventType.PAYMENT_SUCCESS.value
    data: dict[str, Any] | None = None


def _serialize(row, *, reveal_secret: bool = False) -> dict:
    return {
        "id": row.id,
        "url": row.url,
        "description": row.description,
        "events": row.events or [],
        "environment": row.environment,
        "secret": row.secret if reveal_secret else webhook_service.mask_secret(row.secret),
        "status": row.status,
        "createdAt": row.created_at,
    }


@router.post("", response_model=Webhook, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: CreateWebhookRequest,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> dict:
    row = await webhook_service.create_webhook(
        db,
        user_id=user.user_id,
        url=str(payload.url),
        description=payload.description,
        events=payload.events,
        environment=payload.environment,
    )
    await audit.record(
        db,
        request=request,
        actor_user_id=user.user_id,
        action="webhook.create",
        target_type="webhook",
        target_id=row.id,
        environment=row.environment,
        metadata={"url": row.url, "events": row.events or []},
    )
    await db.commit()
    return _serialize(row, reveal_secret=True)


@router.get("", response_model=list[Webhook])
async def list_webhooks(
    user: CurrentUser,
    db: DbDep,
    env: EnvironmentDep,
) -> list[dict]:
    rows = await webhook_service.list_webhooks(
        db, user_id=user.user_id, environment=env
    )
    return [_serialize(r) for r in rows]


@router.patch("/{webhook_id}", response_model=Webhook)
async def update_webhook(
    webhook_id: uuid.UUID,
    payload: UpdateWebhookRequest,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> dict:
    row = await webhook_service.get_webhook(db, user_id=user.user_id, webhook_id=webhook_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    changed: list[str] = []
    if payload.url is not None:
        row.url = str(payload.url)
        changed.append("url")
    if payload.description is not None:
        row.description = payload.description
        changed.append("description")
    if payload.events is not None:
        row.events = payload.events
        changed.append("events")
    if payload.status is not None:
        row.status = payload.status
        changed.append("status")
    await audit.record(
        db,
        request=request,
        actor_user_id=user.user_id,
        action="webhook.update",
        target_type="webhook",
        target_id=row.id,
        environment=row.environment,
        metadata={"changed": changed},
    )
    await db.commit()
    await db.refresh(row)
    return _serialize(row)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> None:
    existing = await webhook_service.get_webhook(
        db, user_id=user.user_id, webhook_id=webhook_id
    )
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    env = existing.environment
    if not await webhook_service.delete_webhook(db, user_id=user.user_id, webhook_id=webhook_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    await audit.record(
        db,
        request=request,
        actor_user_id=user.user_id,
        action="webhook.delete",
        target_type="webhook",
        target_id=webhook_id,
        environment=env,
    )
    await db.commit()


@router.get("/{webhook_id}/deliveries", response_model=DeliveryListResponse)
async def list_deliveries(
    webhook_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_: Annotated[str | None, Query(alias="status")] = None,
) -> dict:
    rows, total = await webhook_service.list_deliveries(
        db,
        user_id=user.user_id,
        webhook_id=webhook_id,
        limit=limit,
        offset=offset,
        status=status_,
    )
    return {
        "items": [
            {
                "id": r.id,
                "webhookId": r.webhook_id,
                "eventType": r.event_type,
                "status": r.status,
                "attempt": r.attempt,
                "responseCode": r.response_code,
                "responseBody": r.response_body,
                "createdAt": r.created_at,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{webhook_id}/rotate-secret", response_model=Webhook)
async def rotate_secret(
    webhook_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
) -> dict:
    row = await webhook_service.rotate_secret(
        db, user_id=user.user_id, webhook_id=webhook_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return _serialize(row, reveal_secret=True)


@router.post("/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def send_test_event(
    webhook_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    body: TestEventBody = None,  # type: ignore[assignment]
) -> dict:
    if body is None:
        body = TestEventBody()
    if not is_valid_event_type(body.event_type):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown event type: {body.event_type}",
        )
    webhook = await webhook_service.get_webhook(
        db, user_id=user.user_id, webhook_id=webhook_id
    )
    if webhook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    payload = body.data or {"test": True, "message": "Test event from Ragini Payment Gateway"}
    event_id = await event_emitter.emit(
        db,
        user_id=user.user_id,
        environment=webhook.environment,
        event_type=EventType(body.event_type),
        data=payload,
    )
    await db.commit()
    event_emitter.schedule_fanout(event_id)
    return {"eventId": str(event_id), "queued": True}
