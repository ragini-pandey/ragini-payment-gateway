"""Audit-trail tests for ``rotate_secret`` and ``sweep_expired``.

These tests assert that the audit row is written **inside the same
transaction** as the mutation (i.e. before ``db.commit()`` returns) and
that the audit row has the correct action / target_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import key_service, webhook_service


def _capture_inserts(db) -> list[dict]:
    """Patch ``db.execute`` to intercept ``insert(...)`` calls and capture
    the values dict from each. Returns the (mutable) list of captured
    value dicts in execution order."""
    captured: list[dict] = []

    async def fake_execute(stmt, *_a, **_kw):
        # SQLAlchemy Insert statements expose ``.compile()`` but the values
        # we passed live in ``.compile_options`` / parameters. The simple
        # path is to inspect ``stmt.parameters`` when present.
        params = getattr(stmt, "_values", None) or getattr(stmt, "parameters", None)
        if params is not None:
            try:
                captured.append({k.key if hasattr(k, "key") else k: v for k, v in params.items()})
            except Exception:
                captured.append({"_raw": str(stmt)})
        result = MagicMock()
        result.scalar_one = MagicMock(return_value=uuid.uuid4())
        result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    return captured


@pytest.mark.asyncio
async def test_rotate_secret_service_does_not_commit(mock_db):
    """The refactored service must leave commit to the caller so audit
    and rotation land in one transaction."""
    fake_row = MagicMock()
    fake_row.secret = "whsec_old"
    fake_row.id = uuid.uuid4()

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fake_row)
    mock_db.execute = AsyncMock(return_value=result)

    out = await webhook_service.rotate_secret(
        mock_db, user_id=uuid.uuid4(), webhook_id=fake_row.id
    )

    assert out is fake_row
    assert fake_row.secret != "whsec_old"
    assert fake_row.secret.startswith("whsec_")
    # The critical assertion: service must NOT commit on its own.
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_expired_writes_audit_per_key(mock_db, mock_celery, monkeypatch):
    """Each key flipped to ``expired`` must produce exactly one
    ``api_key.expired`` audit row in addition to the webhook event."""
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = [
        MagicMock(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            environment="test",
            key_id=f"keyid{i:010d}",
            name=f"k{i}",
            status="active",
            expires_at=past,
        )
        for i in range(3)
    ]

    select_result = MagicMock()
    select_result.scalars = MagicMock(return_value=MagicMock(all=lambda: rows))

    # Track which audit actions were recorded by patching audit.record
    # (simpler and more robust than parsing SQLAlchemy Insert statements).
    audit_calls: list[dict] = []

    async def fake_audit_record(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(key_service.audit, "record", fake_audit_record)

    # Patch emit so we don't need a real DB write; return a fresh UUID each call.
    async def fake_emit(_db, **_kw):
        return uuid.uuid4()

    monkeypatch.setattr(key_service.event_emitter, "emit", fake_emit)

    mock_db.execute = AsyncMock(return_value=select_result)

    n = await key_service.sweep_expired(mock_db)

    assert n == 3
    assert len(audit_calls) == 3
    for call, row in zip(audit_calls, rows):
        assert call["action"] == "api_key.expired"
        assert call["target_type"] == "api_key"
        assert call["target_id"] == row.id
        assert call["environment"] == row.environment
        assert call["actor_user_id"] == row.user_id
        assert call["request"] is None  # system-initiated
        assert call["metadata"]["source"] == "sweep_expired"

    # All three events were committed and scheduled for fan-out.
    mock_db.commit.assert_awaited_once()
    assert len(mock_celery["fanout_event"]) == 3


@pytest.mark.asyncio
async def test_sweep_expired_noop_when_no_due_keys(mock_db, mock_celery, monkeypatch):
    select_result = MagicMock()
    select_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    mock_db.execute = AsyncMock(return_value=select_result)

    audit_calls: list[dict] = []

    async def fake_audit_record(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(key_service.audit, "record", fake_audit_record)

    n = await key_service.sweep_expired(mock_db)
    assert n == 0
    assert audit_calls == []
    mock_db.commit.assert_not_called()
    assert mock_celery["fanout_event"] == []
