"""FastAPI dependencies: authentication, DB session, environment switch.

Two trust boundaries:

- :func:`get_current_user` — Supabase JWT; used by dashboard routes.
- :func:`get_current_api_key` — ``rpg_*`` Bearer token; used by public API routes.

Both verify the credential and log the attempt to ``api_key_usage_events``
when applicable. Revoked/expired key attempts trigger a ``security.alert``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.api_key import ApiKey
from app.models.api_key_usage import ApiKeyUsageEvent
from app.security import api_keys as keys
from app.security.jwt import AuthenticatedUser, JWTVerificationError, verify_jwt
from app.services import event_emitter

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Dashboard auth (Supabase JWT)
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_jwt(token)
    except JWTVerificationError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Environment selector (?environment=test|live or X-Environment header)
# ---------------------------------------------------------------------------


async def get_environment(
    environment: Annotated[str | None, Query()] = None,
    x_environment: Annotated[str | None, Header()] = None,
) -> str:
    env = (environment or x_environment or "test").lower()
    if env not in ("test", "live"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "environment must be 'test' or 'live'")
    return env


EnvironmentDep = Annotated[str, Depends(get_environment)]


# ---------------------------------------------------------------------------
# Public-API auth (rpg_* bearer)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthorizedApiKey:
    id: uuid.UUID
    user_id: uuid.UUID
    environment: str
    key_id: str
    name: str


async def _record_usage(
    db: AsyncSession,
    *,
    api_key_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    environment: str | None,
    route: str,
    status_code: int,
    latency_ms: int | None,
    ip: str | None,
    user_agent: str | None,
) -> None:
    await db.execute(
        insert(ApiKeyUsageEvent).values(
            api_key_id=api_key_id,
            user_id=user_id,
            environment=environment,
            route=route,
            status_code=status_code,
            latency_ms=latency_ms,
            ip=ip,
            user_agent=user_agent,
        )
    )


async def get_current_api_key(
    request: Request,
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthorizedApiKey:
    start = time.perf_counter()
    route = request.url.path
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    async def _fail(code: int, msg: str) -> HTTPException:
        await _record_usage(
            db,
            api_key_id=None,
            user_id=None,
            environment=None,
            route=route,
            status_code=code,
            latency_ms=int((time.perf_counter() - start) * 1000),
            ip=ip,
            user_agent=ua,
        )
        await db.commit()
        return HTTPException(code, msg)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise await _fail(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()

    try:
        parsed = keys.parse(token)
    except keys.InvalidApiKey:
        raise await _fail(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    row = (
        await db.execute(select(ApiKey).where(ApiKey.key_id == parsed.key_id))
    ).scalar_one_or_none()

    if row is None:
        raise await _fail(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    if row.environment != parsed.environment:
        # Environment mismatch is treated as an invalid key, no alert needed
        # (the row exists but the prefix was tampered with).
        raise await _fail(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    if not keys.verify(parsed.secret, row.key_hash):
        raise await _fail(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    # Status checks → security-relevant
    if row.status == "revoked":
        event_id = await event_emitter.emit_security_alert(
            db,
            user_id=row.user_id,
            environment=row.environment,
            alert_type="revoked_key_used",
            severity="high",
            api_key_id=row.id,
            details={"route": route, "ip": ip, "user_agent": ua},
        )
        await db.commit()
        # Schedule fanout AFTER commit so the worker sees the row.
        event_emitter.schedule_fanout(event_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key has been revoked")

    if row.status == "expired" or (row.expires_at is not None and row.expires_at.timestamp() < time.time()):
        event_id = await event_emitter.emit_security_alert(
            db,
            user_id=row.user_id,
            environment=row.environment,
            alert_type="expired_key_used",
            severity="medium",
            api_key_id=row.id,
            details={"route": route, "ip": ip},
        )
        await db.commit()
        event_emitter.schedule_fanout(event_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key has expired")

    # Success — log usage and update last_used_at.
    latency_ms = int((time.perf_counter() - start) * 1000)

    # Rate limiting (per-key, fixed-window). Enforced AFTER verification so
    # callers can't probe rate limits with arbitrary garbage tokens.
    from app.config import get_settings
    from app.redis_client import get_redis
    from app.security.rate_limit import check_and_consume

    settings = get_settings()
    redis = get_redis()
    rl = await check_and_consume(
        redis, key_id=row.key_id, limit=settings.rate_limit_per_minute
    )
    if not rl.allowed:
        await _record_usage(
            db,
            api_key_id=row.id,
            user_id=row.user_id,
            environment=row.environment,
            route=route,
            status_code=429,
            latency_ms=latency_ms,
            ip=ip,
            user_agent=ua,
        )
        # Dedupe alerts per (key, 5-min window) so a hammering client doesn't
        # flood security_alerts.
        dedupe_key = f"alert:ratelimit:{row.key_id}:{int(time.time() // 300)}"
        try:
            should_alert = await redis.set(dedupe_key, "1", ex=600, nx=True)
        except Exception:
            should_alert = False
        rate_event_id: uuid.UUID | None = None
        if should_alert:
            rate_event_id = await event_emitter.emit_security_alert(
                db,
                user_id=row.user_id,
                environment=row.environment,
                alert_type="rate_limit_exceeded",
                severity="medium",
                api_key_id=row.id,
                details={
                    "route": route,
                    "limit_per_minute": rl.limit,
                    "count": rl.count,
                    "ip": ip,
                },
            )
        await db.commit()
        if rate_event_id is not None:
            event_emitter.schedule_fanout(rate_event_id)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            headers={"Retry-After": str(rl.retry_after)},
        )

    await _record_usage(
        db,
        api_key_id=row.id,
        user_id=row.user_id,
        environment=row.environment,
        route=route,
        status_code=200,
        latency_ms=latency_ms,
        ip=ip,
        user_agent=ua,
    )
    row.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    # Sliding-window counter for spike detection (best-effort).
    try:
        from app.redis_client import get_redis

        bucket = int(time.time() // 60)
        r = get_redis()
        await r.incr(f"usage:{row.key_id}:{bucket}")
        await r.expire(f"usage:{row.key_id}:{bucket}", 25 * 3600)
    except Exception:
        pass

    return AuthorizedApiKey(
        id=row.id,
        user_id=row.user_id,
        environment=row.environment,
        key_id=row.key_id,
        name=row.name,
    )


CurrentApiKey = Annotated[AuthorizedApiKey, Depends(get_current_api_key)]
