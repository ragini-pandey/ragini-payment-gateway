"""Pytest fixtures: in-memory settings, fakeredis, mocked Celery task queue.

Heavier DB-touching integration tests should be added behind a
``TEST_DATABASE_URL`` env-var gate so they can be skipped when no Postgres
is available. The fixtures here are designed for unit-level tests against
mocked AsyncSession instances; they avoid spinning up a database.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
)
os.environ.setdefault(
    "DATABASE_URL_SYNC", "postgresql+psycopg2://postgres:password@localhost:5432/postgres"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault(
    "API_KEY_PEPPER", "deadbeefcafef00d" * 4  # 64 hex chars / 32 bytes
)
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")

import pytest


@pytest.fixture
def settings():
    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    return get_settings()


@pytest.fixture
def fake_redis():
    """In-memory async Redis stand-in. Requires ``fakeredis``."""
    from fakeredis.aioredis import FakeRedis

    return FakeRedis(decode_responses=False)


@pytest.fixture
def mock_celery(monkeypatch):
    """Capture Celery ``.delay()`` calls instead of enqueueing.

    Returns a dict ``{task_name: [args_tuples]}`` populated as tasks are
    "enqueued". The task objects in their respective modules are patched
    in place so any code path that imports them (including the lazy
    import inside ``event_emitter.schedule_fanout``) is observed.
    """
    calls: dict[str, list[tuple[Any, ...]]] = {
        "fanout_event": [],
        "dispatch_delivery": [],
    }

    from app.workers.tasks import dispatch_delivery as dd_mod
    from app.workers.tasks import fanout_event as fe_mod

    fake_fanout = MagicMock()
    fake_fanout.delay = MagicMock(
        side_effect=lambda *a, **kw: calls["fanout_event"].append(a) or None
    )
    fake_dispatch = MagicMock()
    fake_dispatch.delay = MagicMock(
        side_effect=lambda *a, **kw: calls["dispatch_delivery"].append(a) or None
    )

    monkeypatch.setattr(fe_mod, "fanout_event", fake_fanout)
    monkeypatch.setattr(dd_mod, "dispatch_delivery", fake_dispatch)
    return calls


@pytest.fixture
def mock_db():
    """An ``AsyncSession``-shaped mock.

    ``execute`` returns a result whose ``scalar_one`` /
    ``scalar_one_or_none`` can be primed per-test.
    ``commit``/``rollback``/``refresh`` are AsyncMocks so call counts are
    inspectable.
    """
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db
