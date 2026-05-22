"""Celery application + beat schedule."""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "ragini",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=[
        "app.workers.tasks.fanout_event",
        "app.workers.tasks.dispatch_delivery",
        "app.workers.tasks.scan_anomalies",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,
    task_default_retry_delay=60,
    timezone="UTC",
)

celery_app.conf.beat_schedule = {
    "scan-anomalies-every-minute": {
        "task": "app.workers.tasks.scan_anomalies.scan_anomalies",
        "schedule": 60.0,
    },
    "sweep-expired-keys-every-5-min": {
        "task": "app.workers.tasks.scan_anomalies.sweep_expired_keys",
        "schedule": 300.0,
    },
}
