"""Regression tests for the security-alert fanout fix in ``app.deps``.

Bug: ``get_current_api_key`` was emitting ``security.alert`` events for
revoked / expired / rate-limited keys but never calling
``event_emitter.schedule_fanout``, so subscribed webhooks never received
the event. These tests assert the call happens after the commit.

The tests bypass the real DB by patching the ORM lookup and the
``emit_security_alert`` helper, then exercising the dependency through
its real public surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.deps import get_current_api_key
from app.security import api_keys as keys


def _make_request(path: str = "/v1/payments"):
    req = MagicMock()
    req.url.path = path
    req.client.host = "203.0.113.1"
    req.headers = {"user-agent": "pytest"}
    return req


def _make_key_row(plaintext_gen, *, status: str = "active", expires_at=None):
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_id = uuid.uuid4()
    row.environment = plaintext_gen.environment
    row.key_id = plaintext_gen.key_id
    row.key_hash = plaintext_gen.key_hash
    row.name = "test-key"
    row.status = status
    row.expires_at = expires_at
    row.last_used_at = None
    return row


def _result(value):
    """Build a fake SQLAlchemy result wrapping ``value`` for
    ``scalar_one_or_none``."""
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=value)
    return r


async def _call_dep(token: str, db, request) -> object:
    return await get_current_api_key(
        request=request,
        db=db,
        authorization=f"Bearer {token}",
    )


@pytest.mark.asyncio
async def test_revoked_key_schedules_fanout(settings, mock_db, mock_celery, monkeypatch):
    gen = keys.generate("test")
    row = _make_key_row(gen, status="revoked")
    # First execute() is the usage-event insert (returns nothing useful),
    # second is the ApiKey lookup. We just always return the row for any
    # SELECT and ignore INSERTs.
    mock_db.execute = AsyncMock(side_effect=lambda *a, **kw: _result(row))

    event_id = uuid.uuid4()
    fake_emit = AsyncMock(return_value=event_id)
    monkeypatch.setattr("app.deps.event_emitter.emit_security_alert", fake_emit)

    with pytest.raises(HTTPException) as exc:
        await _call_dep(gen.plaintext, mock_db, _make_request())

    assert exc.value.status_code == 401
    fake_emit.assert_awaited_once()
    # The critical assertion: fanout MUST be scheduled.
    assert (str(event_id),) in mock_celery["fanout_event"], (
        "schedule_fanout was not called for revoked-key security alert; "
        "subscribers will not receive the event."
    )


@pytest.mark.asyncio
async def test_expired_key_schedules_fanout(settings, mock_db, mock_celery, monkeypatch):
    gen = keys.generate("test")
    past = datetime.now(timezone.utc) - timedelta(days=1)
    row = _make_key_row(gen, status="active", expires_at=past)
    mock_db.execute = AsyncMock(side_effect=lambda *a, **kw: _result(row))

    event_id = uuid.uuid4()
    fake_emit = AsyncMock(return_value=event_id)
    monkeypatch.setattr("app.deps.event_emitter.emit_security_alert", fake_emit)

    with pytest.raises(HTTPException) as exc:
        await _call_dep(gen.plaintext, mock_db, _make_request())

    assert exc.value.status_code == 401
    fake_emit.assert_awaited_once()
    assert (str(event_id),) in mock_celery["fanout_event"]


@pytest.mark.asyncio
async def test_rate_limited_request_schedules_fanout(
    settings, mock_db, mock_celery, fake_redis, monkeypatch
):
    gen = keys.generate("test")
    row = _make_key_row(gen, status="active")
    mock_db.execute = AsyncMock(side_effect=lambda *a, **kw: _result(row))

    monkeypatch.setattr("app.deps.get_redis", lambda: fake_redis, raising=False)
    # The rate limiter is imported lazily inside the dependency; patch both
    # the redis_client module and the rate_limit shortcut.
    monkeypatch.setattr("app.redis_client.get_redis", lambda: fake_redis)

    # Force the limit to 0 so the very first request trips it.
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 0, raising=False)

    event_id = uuid.uuid4()
    fake_emit = AsyncMock(return_value=event_id)
    monkeypatch.setattr("app.deps.event_emitter.emit_security_alert", fake_emit)

    with pytest.raises(HTTPException) as exc:
        await _call_dep(gen.plaintext, mock_db, _make_request())

    assert exc.value.status_code == 429
    fake_emit.assert_awaited_once()
    assert (str(event_id),) in mock_celery["fanout_event"]


@pytest.mark.asyncio
async def test_rate_limit_dedup_suppresses_second_alert(
    settings, mock_db, mock_celery, fake_redis, monkeypatch
):
    """Two rapid 429s in the same 5-minute window must produce only ONE
    fanout event (the dedup gate in deps.py)."""
    gen = keys.generate("test")
    row = _make_key_row(gen, status="active")
    mock_db.execute = AsyncMock(side_effect=lambda *a, **kw: _result(row))

    monkeypatch.setattr("app.redis_client.get_redis", lambda: fake_redis)
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 0, raising=False)

    fake_emit = AsyncMock(side_effect=lambda *a, **kw: uuid.uuid4())
    monkeypatch.setattr("app.deps.event_emitter.emit_security_alert", fake_emit)

    for _ in range(3):
        with pytest.raises(HTTPException):
            await _call_dep(gen.plaintext, mock_db, _make_request())

    # Only the first 429 in the window emits an alert + schedules fanout.
    assert fake_emit.await_count == 1
    assert len(mock_celery["fanout_event"]) == 1
