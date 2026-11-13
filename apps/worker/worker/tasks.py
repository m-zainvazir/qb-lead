"""Background tasks. Every task must be idempotent: it may run twice."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from worker import compiler
from worker.celery_app import app

log = logging.getLogger(__name__)


@app.task(name="worker.tasks.heartbeat")  # type: ignore[untyped-decorator]
def heartbeat() -> str:
    now = datetime.now(UTC).isoformat()
    log.info("heartbeat", extra={"at": now})
    return now


@app.task(  # type: ignore[untyped-decorator]
    name="worker.tasks.compile_profile",
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    soft_time_limit=240,
    time_limit=300,
)
def compile_profile(tenant_id: str) -> str:
    try:
        return compiler.compile_profile(UUID(tenant_id))
    except OSError:
        raise  # network or model download problem: retried with backoff
    except Exception as exc:
        log.exception("profile_compile_failed", extra={"tenant_id": tenant_id})
        compiler.mark_failed(UUID(tenant_id), f"{type(exc).__name__}: {exc}")
        raise


@app.task(name="worker.tasks.compile_pending_profiles")  # type: ignore[untyped-decorator]
def compile_pending_profiles() -> int:
    """Safety net: profiles changed through REST, or whose job was lost, get compiled."""
    tenants = compiler.pending_tenants()
    for tenant_id in tenants:
        compile_profile.delay(str(tenant_id))
    return len(tenants)


@app.task(  # type: ignore[untyped-decorator]
    name="worker.tasks.process_portfolio_item",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=5,
    soft_time_limit=120,
    time_limit=180,
)
def process_portfolio_item(item_id: str) -> str:
    from worker import portfolio

    return portfolio.process_item(UUID(item_id))
