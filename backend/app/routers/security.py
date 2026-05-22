"""Security alerts dashboard route."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUser, DbDep, EnvironmentDep
from app.models.security_alert import SecurityAlert
from app.schemas.security import SecurityAlert as SecurityAlertSchema

router = APIRouter(prefix="/v1/security", tags=["security"])


@router.get("/alerts", response_model=list[SecurityAlertSchema])
async def list_alerts(
    user: CurrentUser,
    db: DbDep,
    env: EnvironmentDep,
    limit: int = 100,
) -> list[SecurityAlert]:
    rows = (
        await db.execute(
            select(SecurityAlert)
            .where(SecurityAlert.user_id == user.user_id, SecurityAlert.environment == env)
            .order_by(SecurityAlert.created_at.desc())
            .limit(min(limit, 500))
        )
    ).scalars().all()
    return list(rows)
