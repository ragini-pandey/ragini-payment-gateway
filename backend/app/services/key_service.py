"""API key lifecycle: create, list, revoke, masked-list helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import EventType
from app.models.api_key import ApiKey
from app.security import api_keys as keys
from app.services import audit, event_emitter


async def create_key(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    name: str,
    environment: str,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Returns (row, plaintext_key). Plaintext is ONLY returned here."""
    if environment not in ("test", "live"):
        raise ValueError("environment must be 'test' or 'live'")
    gen = keys.generate(environment)  # type: ignore[arg-type]
    row = ApiKey(
        user_id=user_id,
        name=name,
        environment=environment,
        key_id=gen.key_id,
        key_prefix=gen.key_prefix,
        key_hash=gen.key_hash,
        last_four=gen.last_four,
        status="active",
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row, gen.plaintext


async def list_keys(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    environment: str | None = None,
) -> list[ApiKey]:
    stmt = select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    if environment is not None:
        stmt = stmt.where(ApiKey.environment == environment)
    return list((await db.execute(stmt)).scalars().all())


async def revoke_key(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    key_db_id: uuid.UUID,
    reason: str | None,
) -> ApiKey | None:
    row = (
        await db.execute(
            select(ApiKey).where(ApiKey.id == key_db_id, ApiKey.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None or row.status == "revoked":
        return row
    row.status = "revoked"
    row.revoked_at = datetime.now(timezone.utc)
    row.revoked_reason = reason
    event_id = await event_emitter.emit(
        db,
        user_id=row.user_id,
        environment=row.environment,
        event_type=EventType.API_KEY_REVOKED,
        data={
            "api_key_id": str(row.id),
            "key_id": row.key_id,
            "name": row.name,
            "reason": reason,
        },
    )
    await db.commit()
    event_emitter.schedule_fanout(event_id)
    return row


async def sweep_expired(db: AsyncSession) -> int:
    """Flip any past-due keys to 'expired'. Emits api_key.expired for each."""
    now = datetime.now(timezone.utc)
    rows = list(
        (
            await db.execute(
                select(ApiKey).where(
                    ApiKey.status == "active",
                    ApiKey.expires_at.isnot(None),
                    ApiKey.expires_at < now,
                )
            )
        )
        .scalars()
        .all()
    )
    event_ids: list[uuid.UUID] = []
    for row in rows:
        row.status = "expired"
        event_ids.append(
            await event_emitter.emit(
                db,
                user_id=row.user_id,
                environment=row.environment,
                event_type=EventType.API_KEY_EXPIRED,
                data={"api_key_id": str(row.id), "key_id": row.key_id, "name": row.name},
            )
        )
        # System-initiated audit entry: no Request context, attribute to the
        # key owner with a sentinel user_agent so operators can distinguish
        # automated transitions from user-initiated ones.
        await audit.record(
            db,
            request=None,
            actor_user_id=row.user_id,
            action="api_key.expired",
            target_type="api_key",
            target_id=row.id,
            environment=row.environment,
            metadata={"key_id": row.key_id, "name": row.name, "source": "sweep_expired"},
        )
    if rows:
        await db.commit()
        for eid in event_ids:
            event_emitter.schedule_fanout(eid)
    return len(rows)


def to_dto(row: ApiKey) -> dict:
    """Return the camelCase-safe public projection (without plaintext)."""
    return {
        "id": row.id,
        "name": row.name,
        "environment": row.environment,
        "keyPrefix": row.key_prefix,
        "lastFour": row.last_four,
        "status": row.status,
        "createdAt": row.created_at,
        "lastUsedAt": row.last_used_at,
        "expiresAt": row.expires_at,
        "revokedAt": row.revoked_at,
    }
