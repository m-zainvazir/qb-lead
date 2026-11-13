"""Queue background jobs from the API without importing the worker.

Enqueueing never fails a request: if Redis is down, the worker's periodic sweep
(for example `compile_pending_profiles`) still finds the work later.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from celery import Celery

from core.settings import get_settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> Celery:
    app = Celery("leadgen-client", broker=get_settings().redis_url.get_secret_value())
    app.conf.update(
        broker_connection_timeout=3,
        broker_connection_retry=False,
        task_publish_retry=False,
    )
    return app


def _send(name: str, args: tuple[Any, ...]) -> None:
    _client().send_task(name, args=list(args))


async def enqueue(name: str, *args: Any) -> bool:
    try:
        await asyncio.wait_for(asyncio.to_thread(_send, name, args), timeout=5)
        return True
    except Exception:
        log.warning("enqueue_failed", extra={"task": name}, exc_info=True)
        return False
