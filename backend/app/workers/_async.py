"""Shared async-in-Celery helper.

Celery's standard worker pool is sync, but our code is async. We bridge with a
single per-process event loop using ``asyncio.run`` per task. For higher
throughput later, swap to ``gevent`` or a dedicated async worker.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: Awaitable[T]) -> T:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():  # pragma: no cover
            raise RuntimeError("run_async called from a running loop")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)  # type: ignore[arg-type]
