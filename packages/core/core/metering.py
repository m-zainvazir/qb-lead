"""metered_call(): the one wrapper every paid (or metered) outside call goes through.

It times the call, records units and cost in `usage_events` (also when the call fails),
and re-raises errors. Module 10 adds the monthly spending cap check here, so callers
get it without changing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from core.db import system_db_sync

log = logging.getLogger(__name__)


def metered_call[T](
    fn: Callable[[], T],
    *,
    provider: str,
    operation: str,
    tenant_id: UUID | str | None,
    units: float,
    unit: str,
    unit_cost_usd: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> T:
    start = time.perf_counter()
    succeeded = False
    try:
        result = fn()
        succeeded = True
        return result
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        cost = round(units * unit_cost_usd, 6) if succeeded else 0.0
        try:
            with (
                system_db_sync() as conn
            ):  # own short transaction: recorded even if the caller rolls back
                conn.execute(
                    "insert into public.usage_events (tenant_id, provider, operation, units, unit,"
                    " cost_usd, succeeded, duration_ms, metadata)"
                    " values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        tenant_id,
                        provider,
                        operation,
                        units,
                        unit,
                        cost,
                        succeeded,
                        duration_ms,
                        Jsonb(metadata or {}),
                    ),
                )
        except Exception:
            log.error("usage_event_write_failed", extra={"operation": operation}, exc_info=True)
