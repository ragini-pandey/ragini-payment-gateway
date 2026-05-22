"""Async SQLAlchemy engine + session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=10,
    pool_recycle=1800,
    # Supabase Supavisor transaction pooler (port 6543) does not support
    # prepared statements; disable asyncpg's statement cache.
    # ``server_settings`` enforces a 5-second statement timeout (queries that
    # legitimately need longer must opt out with ``SET LOCAL`` inside a tx)
    # and tags the connection with a human-readable application name for
    # easier pg_stat_activity debugging.
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "server_settings": {
            "statement_timeout": "5000",
            "application_name": "ragini-api",
        },
    },
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
