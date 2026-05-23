"""Tests for the sliding-window per-API-key rate limiter.

Covers:
  - Allows requests strictly below the limit.
  - Denies the request that would exceed the limit.
  - ``retry_after`` reflects the time until the oldest in-window entry
    ages out (sliding-window precision, not minute-boundary).
  - Old entries past ``window_seconds`` no longer consume budget.
  - Buckets are scoped per ``key_id`` and do not bleed across keys.
  - Concurrent allowed calls do not over-admit due to score collisions
    (members are deduplicated via the random suffix).
  - Allowed branch returns the new in-window count; denied branch returns
    the unchanged count.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.security.rate_limit import check_and_consume


@pytest.mark.asyncio
async def test_allows_up_to_limit(fake_redis):
    results = []
    for _ in range(3):
        results.append(
            await check_and_consume(
                fake_redis, key_id="k1", limit=3, window_seconds=60
            )
        )
    assert [r.allowed for r in results] == [True, True, True]
    assert [r.count for r in results] == [1, 2, 3]
    assert all(r.limit == 3 for r in results)
    assert all(r.retry_after == 0 for r in results)


@pytest.mark.asyncio
async def test_denies_request_over_limit(fake_redis):
    for _ in range(2):
        await check_and_consume(
            fake_redis, key_id="k1", limit=2, window_seconds=60
        )

    denied = await check_and_consume(
        fake_redis, key_id="k1", limit=2, window_seconds=60
    )

    assert denied.allowed is False
    assert denied.count == 2
    assert denied.limit == 2
    # Just-added entry expires ~60s from now; retry_after should be near window.
    assert 1 <= denied.retry_after <= 61


@pytest.mark.asyncio
async def test_zero_limit_denies_first_request(fake_redis):
    r = await check_and_consume(
        fake_redis, key_id="k1", limit=0, window_seconds=60
    )
    assert r.allowed is False
    assert r.count == 0
    assert r.retry_after == 1  # nothing in the bucket → fallback retry


@pytest.mark.asyncio
async def test_keys_isolated_by_key_id(fake_redis):
    await check_and_consume(fake_redis, key_id="k1", limit=1, window_seconds=60)
    # k1 is full…
    r_k1 = await check_and_consume(
        fake_redis, key_id="k1", limit=1, window_seconds=60
    )
    # …but k2 is independent.
    r_k2 = await check_and_consume(
        fake_redis, key_id="k2", limit=1, window_seconds=60
    )
    assert r_k1.allowed is False
    assert r_k2.allowed is True


@pytest.mark.asyncio
async def test_old_entries_freed_by_sliding_window(fake_redis):
    """Manually backdate the in-bucket entry past the window and confirm budget frees."""
    await check_and_consume(
        fake_redis, key_id="k1", limit=1, window_seconds=60
    )
    denied = await check_and_consume(
        fake_redis, key_id="k1", limit=1, window_seconds=60
    )
    assert denied.allowed is False

    # Backdate every member of the bucket to before the window.
    bucket = b"ratelimit:k1"
    members = await fake_redis.zrange(bucket, 0, -1, withscores=True)
    assert members, "expected at least one member"
    pipe = fake_redis.pipeline()
    for member, _score in members:
        pipe.zadd(bucket, {member: time.time() - 120.0})
    await pipe.execute()

    # New request must now be admitted.
    after = await check_and_consume(
        fake_redis, key_id="k1", limit=1, window_seconds=60
    )
    assert after.allowed is True
    assert after.count == 1


@pytest.mark.asyncio
async def test_retry_after_decreases_as_oldest_ages(fake_redis):
    """Older first entry → smaller retry_after."""
    await check_and_consume(
        fake_redis, key_id="k1", limit=1, window_seconds=60
    )

    # Age the oldest entry to ~50s ago, so ~10s remain until it frees.
    bucket = b"ratelimit:k1"
    members = await fake_redis.zrange(bucket, 0, -1, withscores=True)
    pipe = fake_redis.pipeline()
    for member, _score in members:
        pipe.zadd(bucket, {member: time.time() - 50.0})
    await pipe.execute()

    denied = await check_and_consume(
        fake_redis, key_id="k1", limit=1, window_seconds=60
    )
    assert denied.allowed is False
    # ~10s left in the window; allow a small fudge for timing.
    assert 5 <= denied.retry_after <= 15


@pytest.mark.asyncio
async def test_concurrent_admissions_do_not_exceed_limit(fake_redis):
    limit = 5
    tasks = [
        check_and_consume(fake_redis, key_id="k1", limit=limit, window_seconds=60)
        for _ in range(20)
    ]
    results = await asyncio.gather(*tasks)
    admitted = [r for r in results if r.allowed]
    rejected = [r for r in results if not r.allowed]

    assert len(admitted) == limit
    assert len(rejected) == 20 - limit
    # Every rejection must report the limit unchanged.
    assert all(r.count == limit and r.limit == limit for r in rejected)
