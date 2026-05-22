"""Append-only audit trail for dashboard mutations.

Every state-changing dashboard endpoint (create/update/revoke/delete/rotate)
should call :func:`record` *inside the same transaction* as the mutation so
either both succeed or both roll back. We deliberately do not commit here.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


async def record(
    db: AsyncSession,
    *,
    request: Request | None,
    actor_user_id: uuid.UUID | str,
    action: str,
    target_type: str,
    target_id: uuid.UUID | str,
    environment: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    ip: str | None = None
    user_agent: str | None = None
    if request is not None:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    await db.execute(
        insert(AuditEvent).values(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            environment=environment,
            metadata=metadata or {},
            ip=ip,
            user_agent=user_agent,
        )
    )
