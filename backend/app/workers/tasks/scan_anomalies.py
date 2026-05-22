"""Periodic anomaly detection + expired-key sweep.

Two simple production-grade signals:

1. **Request spikes** — for every ``key_id`` with activity in the last minute
   (detected via Redis ``usage:<key_id>:<bucket>`` counters), compare the
   current 1-min count to a 24h per-minute average. If above
   ``max(20, 5 × baseline)`` AND no alert was emitted in the last 10 minutes,
   emit ``security.alert`` with type ``request_spike``.
2. **Expired keys** — flip past-due keys to ``status='expired'`` and emit
   ``api_key.expired``.
"""

from __future__ import annotations

import time

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.api_key import ApiKey
from app.redis_client import get_redis
from app.services import event_emitter
from app.services.key_service import sweep_expired
from app.workers._async import run_async
from app.workers.celery_app import celery_app

SPIKE_FLOOR = 20         # ignore tiny absolute volumes
SPIKE_MULTIPLIER = 5.0   # current must be ≥ multiplier × baseline
DEDUP_TTL_SECONDS = 600  # 10 min between alerts for the same key


async def _scan() -> int:
    redis = get_redis()
    now_bucket = int(time.time() // 60)
    # Scan recent usage buckets. We look at the previous full minute to avoid
    # counting an in-progress bucket.
    target_bucket = now_bucket - 1
    pattern = f"usage:*:{target_bucket}"
    alerts_emitted = 0

    keys_seen: list[tuple[str, int]] = []
    async for key in redis.scan_iter(match=pattern, count=500):
        try:
            count = int(await redis.get(key) or 0)
        except (TypeError, ValueError):
            continue
        # Extract key_id from "usage:<key_id>:<bucket>"
        parts = key.split(":")
        if len(parts) != 3:
            continue
        keys_seen.append((parts[1], count))

    if not keys_seen:
        return 0

    async with AsyncSessionLocal() as db:
        for key_id, current in keys_seen:
            if current < SPIKE_FLOOR:
                continue

            # 24h baseline: average per-minute over the last 1440 buckets.
            # We approximate by summing a sample window (last 60 buckets) and
            # extrapolating. Cheap and good enough for v1.
            window_total = 0
            window_buckets = 60
            for b in range(target_bucket - window_buckets, target_bucket):
                v = await redis.get(f"usage:{key_id}:{b}")
                if v is not None:
                    try:
                        window_total += int(v)
                    except ValueError:
                        pass
            baseline = window_total / window_buckets if window_buckets else 0.0
            threshold = max(SPIKE_FLOOR, int(SPIKE_MULTIPLIER * baseline))
            if current < threshold:
                continue

            dedup_key = f"alert:spike:{key_id}"
            if await redis.set(dedup_key, "1", ex=DEDUP_TTL_SECONDS, nx=True):
                row = (
                    await db.execute(select(ApiKey).where(ApiKey.key_id == key_id))
                ).scalar_one_or_none()
                if row is None:
                    continue
                event_id = await event_emitter.emit_security_alert(
                    db,
                    user_id=row.user_id,
                    environment=row.environment,
                    alert_type="request_spike",
                    severity="medium",
                    api_key_id=row.id,
                    details={
                        "key_id": key_id,
                        "count_1m": current,
                        "baseline_1m": round(baseline, 2),
                        "threshold": threshold,
                    },
                )
                await db.commit()
                event_emitter.schedule_fanout(event_id)
                alerts_emitted += 1
    return alerts_emitted


@celery_app.task(name="app.workers.tasks.scan_anomalies.scan_anomalies")
def scan_anomalies() -> int:
    return run_async(_scan())


async def _sweep_expired() -> int:
    async with AsyncSessionLocal() as db:
        return await sweep_expired(db)


@celery_app.task(name="app.workers.tasks.scan_anomalies.sweep_expired_keys")
def sweep_expired_keys() -> int:
    return run_async(_sweep_expired())
