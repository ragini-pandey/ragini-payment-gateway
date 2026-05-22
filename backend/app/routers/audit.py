"""Audit-log read endpoint (dashboard, Supabase JWT auth)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.deps import CurrentUser, DbDep
from app.models.audit_event import AuditEvent

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("")
async def list_audit_events(
    user: CurrentUser,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query()] = None,
    target_type: Annotated[str | None, Query()] = None,
) -> dict:
    base = select(AuditEvent).where(AuditEvent.actor_user_id == user.user_id)
    if action:
        base = base.where(AuditEvent.action == action)
    if target_type:
        base = base.where(AuditEvent.target_type == target_type)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = list(
        (
            await db.execute(
                base.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "targetType": r.target_type,
                "targetId": str(r.target_id),
                "environment": r.environment,
                "metadata": r.metadata_,
                "ip": r.ip,
                "userAgent": r.user_agent,
                "createdAt": r.created_at,
            }
            for r in rows
        ],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }
