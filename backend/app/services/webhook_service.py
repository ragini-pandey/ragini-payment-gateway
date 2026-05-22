"""Webhook CRUD + delivery accessors."""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import Webhook
from app.models.webhook_delivery import WebhookDelivery

_SECRET_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
_SECRET_LEN = 48


def _generate_secret() -> str:
    return "whsec_" + "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(_SECRET_LEN))


async def create_webhook(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    url: str,
    description: str | None,
    events: list[str],
    environment: str,
) -> Webhook:
    row = Webhook(
        user_id=user_id,
        environment=environment,
        url=url,
        description=description,
        events=events,
        secret=_generate_secret(),
        status="active",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_webhooks(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    environment: str | None = None,
) -> list[Webhook]:
    stmt = select(Webhook).where(Webhook.user_id == user_id).order_by(Webhook.created_at.desc())
    if environment is not None:
        stmt = stmt.where(Webhook.environment == environment)
    return list((await db.execute(stmt)).scalars().all())


async def get_webhook(
    db: AsyncSession, *, user_id: uuid.UUID | str, webhook_id: uuid.UUID
) -> Webhook | None:
    return (
        await db.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == user_id)
        )
    ).scalar_one_or_none()


async def delete_webhook(
    db: AsyncSession, *, user_id: uuid.UUID | str, webhook_id: uuid.UUID
) -> bool:
    res = await db.execute(
        delete(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == user_id)
    )
    await db.commit()
    return (res.rowcount or 0) > 0


async def list_deliveries(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    webhook_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[WebhookDelivery], int]:
    base = select(WebhookDelivery).where(
        WebhookDelivery.webhook_id == webhook_id,
        WebhookDelivery.user_id == user_id,
    )
    if status:
        base = base.where(WebhookDelivery.status == status)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = list(
        (
            await db.execute(
                base.order_by(WebhookDelivery.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, int(total)


async def rotate_secret(
    db: AsyncSession, *, user_id: uuid.UUID | str, webhook_id: uuid.UUID
) -> Webhook | None:
    row = await get_webhook(db, user_id=user_id, webhook_id=webhook_id)
    if row is None:
        return None
    row.secret = _generate_secret()
    await db.commit()
    await db.refresh(row)
    return row


def mask_secret(secret: str) -> str:
    if not secret or len(secret) < 10:
        return "whsec_…"
    return f"{secret[:10]}…{secret[-4:]}"
