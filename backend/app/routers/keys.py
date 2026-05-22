"""API key management routes (dashboard, Supabase JWT auth)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import case, func, select

from app.deps import CurrentUser, DbDep, EnvironmentDep
from app.models.api_key_usage import ApiKeyUsageEvent
from app.schemas.api_key import ApiKey, ApiKeyWithSecret, CreateApiKeyRequest, RevokeApiKeyRequest
from app.services import audit, key_service

router = APIRouter(prefix="/v1/keys", tags=["api-keys"])


def _serialize(row, *, plaintext: str | None = None) -> dict:
    base = key_service.to_dto(row)
    if plaintext is not None:
        base["key"] = plaintext
    return base


@router.post("", response_model=ApiKeyWithSecret, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: CreateApiKeyRequest,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> dict:
    row, plaintext = await key_service.create_key(
        db,
        user_id=user.user_id,
        name=payload.name,
        environment=payload.environment,
        expires_at=payload.expires_at,
    )
    await audit.record(
        db,
        request=request,
        actor_user_id=user.user_id,
        action="api_key.create",
        target_type="api_key",
        target_id=row.id,
        environment=row.environment,
        metadata={"name": row.name, "expiresAt": row.expires_at.isoformat() if row.expires_at else None},
    )
    await db.commit()
    return _serialize(row, plaintext=plaintext)


@router.get("", response_model=list[ApiKey])
async def list_keys(
    user: CurrentUser,
    db: DbDep,
    env: EnvironmentDep,
) -> list[dict]:
    rows = await key_service.list_keys(db, user_id=user.user_id, environment=env)
    return [_serialize(r) for r in rows]


@router.post("/{key_db_id}/revoke", response_model=ApiKey)
async def revoke_key(
    key_db_id: uuid.UUID,
    payload: RevokeApiKeyRequest,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> dict:
    row = await key_service.revoke_key(
        db,
        user_id=user.user_id,
        key_db_id=key_db_id,
        reason=payload.reason,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await audit.record(
        db,
        request=request,
        actor_user_id=user.user_id,
        action="api_key.revoke",
        target_type="api_key",
        target_id=row.id,
        environment=row.environment,
        metadata={"reason": payload.reason},
    )
    await db.commit()
    return _serialize(row)


@router.get("/{key_db_id}/usage")
async def get_usage(
    key_db_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    range: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
) -> dict:
    spans = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    if range not in spans:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "range must be one of 24h, 7d, 30d")
    since = datetime.now(timezone.utc) - spans[range]
    bucket = func.date_trunc("hour" if range == "24h" else "day", ApiKeyUsageEvent.created_at)
    rows = (
        await db.execute(
            select(
                bucket.label("ts"),
                func.count().label("total"),
                func.sum(
                    case((ApiKeyUsageEvent.status_code >= 400, 1), else_=0)
                ).label("errors"),
            )
            .where(
                ApiKeyUsageEvent.api_key_id == key_db_id,
                ApiKeyUsageEvent.user_id == user.user_id,
                ApiKeyUsageEvent.created_at >= since,
            )
            .group_by(bucket)
            .order_by(bucket)
        )
    ).all()
    return {
        "range": range,
        "points": [
            {"timestamp": r.ts.isoformat(), "total": int(r.total), "errors": int(r.errors or 0)}
            for r in rows
        ],
    }
