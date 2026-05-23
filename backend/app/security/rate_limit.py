"""Per-API-key rate limiting using a sliding-window log.

Algorithm (Redis sorted set):
  - Sorted set ``ratelimit:<key_id>`` stores one member per in-flight request;
    the score is the request timestamp (float seconds, microsecond precision).
  - A Lua script atomically:
      1. Removes all members older than ``now - window_seconds`` (expired).
      2. Counts the remaining live members.
      3. If count < limit, adds the new request member and returns allowed.
      4. Refreshes the key TTL so idle keys self-expire from Redis.

  Unlike fixed-window counting this guarantees at most ``limit`` requests in
  any rolling ``window_seconds``-second window, with no boundary-burst problem.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    retry_after: int


# Atomic sliding-window check-and-consume in Lua so the
# read-modify-write is safe under concurrent requests.
_SLIDING_WINDOW_LUA = """
local key    = KEYS[1]
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
local member = ARGV[4]
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = tonumber(redis.call('ZCARD', key))

if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window + 10)
    return {1, count + 1}
else
    redis.call('EXPIRE', key, window + 10)
    return {0, count}
end
"""


async def check_and_consume(
    redis: Redis, *, key_id: str, limit: int, window_seconds: int = 60
) -> RateLimitResult:
    now = time.time()
    bucket_key = f"ratelimit:{key_id}"
    # Unique member prevents duplicate-score collisions under concurrency.
    member = f"{now:.6f}-{uuid.uuid4().hex[:8]}"

    result = await redis.eval(
        _SLIDING_WINDOW_LUA,
        1,
        bucket_key,
        str(now),
        str(window_seconds),
        str(limit),
        member,
    )

    allowed = bool(result[0])
    count = int(result[1])

    if not allowed:
        # Tell the client when the oldest in-window entry ages out.
        oldest = await redis.zrange(bucket_key, 0, 0, withscores=True)
        if oldest:
            oldest_ts = float(oldest[0][1])
            retry_after = max(1, int(window_seconds - (now - oldest_ts)) + 1)
        else:
            retry_after = 1
        return RateLimitResult(
            allowed=False, count=count, limit=limit, retry_after=retry_after
        )

    return RateLimitResult(allowed=True, count=count, limit=limit, retry_after=0)
