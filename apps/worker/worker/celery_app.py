"""Celery application. Run the worker with `celery -A worker.celery_app worker`
and exactly one scheduler with `celery -A worker.celery_app beat`."""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.signals import setup_logging

from core.logging import configure_logging
from core.settings import get_settings

settings = get_settings()

app = Celery("worker", broker=settings.redis_url.get_secret_value(), include=["worker.tasks"])
app.conf.update(
    task_acks_late=True,  # a task that crashes mid-run is redelivered...
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,  # ...so every task must be safe to run twice
    task_time_limit=300,
    task_soft_time_limit=270,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "heartbeat": {"task": "worker.tasks.heartbeat", "schedule": 60.0},
    },
)


@setup_logging.connect  # type: ignore[untyped-decorator]
def _setup_logging(**_kwargs: Any) -> None:
    configure_logging(settings.log_level)
