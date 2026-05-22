"""Pytest fixtures: in-memory settings + fakeredis."""

from __future__ import annotations

import os

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
