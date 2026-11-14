"""metered_call(): the one wrapper every paid (or metered) outside call goes through.

* Before the call: when the call belongs to a source, it refuses (CapReached) if this
  month's recorded spend plus this call's cost would pass the source's monthly cap.
* After the call: it records provider, units, cost, tenant, run and source in
  `usage_events` (also when the call fails) and re-raises errors.

Module 10 adds per-company caps here, so callers get them without changing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from core.db import system_db_sync

log = logging.getLogger(__name__)


class CapReached(Exception):
    """The monthly cap for this source would be passed; the call was not made."""


def spent_this_month(source_key: str) -> tuple[Decimal, Decimal]:
    """(spent so far this calendar month in UTC, monthly cap) for a source."""
    with system_db_sync() as conn:
        row = conn.execute(
            "select s.monthly_cap_usd as cap,"
            " coalesce((select sum(u.cost_usd) from public.usage_events u"
            "   where u.source_key = s.key"
            "     and u.created_at >= date_trunc('month', now() at time zone 'utc')"
            "                          at time zone 'utc'), 0) as spent"
            " from public.sources s where s.key = %s",
            (source_key,),
        ).fetchone()
    if row is None:
        raise CapReached(f"unknown source {source_key}")
    return Decimal(row["spent"]), Decimal(row["cap"])


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
    source_key: str | None = None,
    run_id: UUID | str | None = None,
) -> T:
    planned = Decimal(str(round(units * unit_cost_usd, 6)))
    if source_key is not None:
        spent, cap = spent_this_month(source_key)
        if spent + planned > cap:
            raise CapReached(
                f"{source_key}: monthly cap ${cap} reached (spent ${spent}, next call ${planned})"
            )

    start = time.perf_counter()
    succeeded = False
    try:
        result = fn()
        succeeded = True
        return result
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        cost = planned if succeeded else Decimal(0)
        try:
            # Own short transaction: recorded even if the caller's transaction rolls back.
            with system_db_sync() as conn:
                conn.execute(
                    "insert into public.usage_events (tenant_id, provider, operation, units, unit,"
                    " cost_usd, succeeded, duration_ms, metadata, source_key, run_id)"
                    " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
                        source_key,
                        run_id,
                    ),
                )
        except Exception:
            log.error("usage_event_write_failed", extra={"operation": operation}, exc_info=True)
