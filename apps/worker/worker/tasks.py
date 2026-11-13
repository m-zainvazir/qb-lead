"""Background tasks. Every task must be idempotent: it may run twice."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from worker.celery_app import app

log = logging.getLogger(__name__)


@app.task(name="worker.tasks.heartbeat")  # type: ignore[untyped-decorator]
def heartbeat() -> str:
    now = datetime.now(UTC).isoformat()
    log.info("heartbeat", extra={"at": now})
    return now
