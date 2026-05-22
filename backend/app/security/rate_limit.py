"""Per-API-key rate limiting (Redis fixed-window).

Algorithm: for each ``key_id`` we keep a counter under
``ratelimit:<key_id>:<unix_minute>``. The first request in a window calls
``INCR`` (which atomically sets the value to 1) and then sets a 70-second TTL,
giving the key a clean slate every minute. Subsequent requests just ``INCR``.
If the post-increment value exceeds the configured limit, the request is
denied and the remaining seconds-in-window are returned so the caller can
populate ``Retry-After``.

This is intentionally simple and correct under concurrency (``INCR`` is
atomic). A token-bucket upgrade is left as future work.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    retry_after: int


async def check_and_consume(
    redis: Redis, *, key_id: str, limit: int, window_seconds: int = 60
) -> RateLimitResult:
    now = int(time.time())
    bucket = now // window_seconds
    bucket_key = f"ratelimit:{key_id}:{bucket}"
    count = await redis.incr(bucket_key)
    if count == 1:
        # Slightly longer TTL than the window so we don't lose the counter
        # at the exact boundary if the second INCR races the EXPIRE.
        await redis.expire(bucket_key, window_seconds + 10)
    if count > limit:
        retry_after = max(1, window_seconds - (now % window_seconds))
        return RateLimitResult(
            allowed=False, count=int(count), limit=limit, retry_after=retry_after
        )
    return RateLimitResult(allowed=True, count=int(count), limit=limit, retry_after=0)
