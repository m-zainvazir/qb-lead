"""Run one source: lock, plan queries, fetch, write raw_items, record the run.

* One source never runs twice at once (advisory lock held for the whole run).
* Fetching the same post twice creates one row (unique on source + external id).
* A capped run stops cleanly as 'capped'; any error marks the run 'failed'. Each source
  runs in its own task, so one failing source never blocks the others.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from core.db import system_db_sync
from core.metering import CapReached
from worker.ingest import planner
from worker.ingest.base import NotConfigured, RawItem, RunContext
from worker.ingest.registry import get_connector

log = logging.getLogger(__name__)
BATCH = 50
FIRST_RUN_LOOKBACK = timedelta(days=3)


def _clean(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = text.replace("\x00", "").strip()
    return text[:limit] or None


def write_items(
    items: Iterable[RawItem],
    *,
    source_key: str,
    run_id: UUID | None,
    visibility: str = "pooled",
    tenant_id: UUID | None = None,
) -> tuple[int, int, list[UUID]]:
    """Insert raw items; duplicates are ignored. Returns (seen, new, new_ids)."""
    seen = new = 0
    new_ids: list[UUID] = []
    batch: list[RawItem] = []

    def flush() -> None:
        nonlocal new
        if not batch:
            return
        with system_db_sync() as conn:
            for item in batch:
                row = conn.execute(
                    "insert into public.raw_items (source_key, external_id, visibility, tenant_id,"
                    " run_id, url, author_handle, author_url, title, body, posted_at, payload)"
                    " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    " on conflict (source_key, external_id) do nothing returning id",
                    (
                        source_key,
                        item.external_id[:300],
                        visibility,
                        tenant_id,
                        run_id,
                        _clean(item.url, 2000),
                        _clean(item.author_handle, 200),
                        _clean(item.author_url, 2000),
                        _clean(item.title, 500),
                        _clean(item.body, 50000),
                        item.posted_at,
                        Jsonb(item.payload),
                    ),
                ).fetchone()
                if row is not None:
                    new += 1
                    new_ids.append(row["id"])
        batch.clear()

    for item in items:
        seen += 1
        batch.append(item)
        if len(batch) >= BATCH:
            flush()
    flush()
    return seen, new, new_ids


def run_source(source_key: str, trigger: str = "schedule") -> dict[str, Any]:
    with system_db_sync() as lock_conn:  # held open for the whole run: the lock lives here
        got = lock_conn.execute(
            "select pg_try_advisory_xact_lock(hashtextextended('source:' || %s, 0)) as ok",
            (source_key,),
        ).fetchone()
        if not got or not got["ok"]:
            return {"source": source_key, "status": "skipped", "reason": "already running"}
        source = lock_conn.execute(
            "select key, connector, kind, risk, enabled, red_override_at, cost_per_call_usd,"
            " max_queries_per_run, settings from public.sources where key = %s",
            (source_key,),
        ).fetchone()
        if source is None:
            return {"source": source_key, "status": "skipped", "reason": "unknown source"}
        if source["kind"] != "pull":
            return {"source": source_key, "status": "skipped", "reason": "push source"}
        if not source["enabled"] and trigger == "schedule":
            return {"source": source_key, "status": "skipped", "reason": "disabled"}
        if source["risk"] == "red" and source["red_override_at"] is None:
            return {
                "source": source_key,
                "status": "skipped",
                "reason": "red source without override",
            }
        return _run(source, trigger)


def _run(source: dict[str, Any], trigger: str) -> dict[str, Any]:
    key = source["key"]
    with system_db_sync() as conn:
        run = conn.execute(
            "insert into public.source_runs (source_key, trigger) values (%s, %s) returning id",
            (key, trigger),
        ).fetchone()
        assert run is not None
        run_id: UUID = run["id"]
        # Search from the last run that really searched: a run with no queries (no compiled
        # profiles yet) must not move the window, or history would be skipped for good.
        last = conn.execute(
            "select max(started_at) as at from public.source_runs"
            " where source_key = %s and status = 'succeeded' and queries > 0",
            (key,),
        ).fetchone()
        since = last["at"] if last and last["at"] else datetime.now(UTC) - FIRST_RUN_LOOKBACK
        connector = get_connector(source["connector"])
        queries = planner.plan(conn, connector.query_family, int(source["max_queries_per_run"]))

    ctx = RunContext(
        source_key=key,
        run_id=run_id,
        settings=dict(source["settings"]),
        cost_per_call_usd=float(source["cost_per_call_usd"]),
    )
    status, error = "succeeded", None
    seen = new = 0
    try:
        seen, new, _ = write_items(
            connector.fetch(queries, since, ctx), source_key=key, run_id=run_id
        )
    except CapReached as exc:
        status, error = "capped", str(exc)
    except NotConfigured as exc:
        status, error = "skipped", str(exc)
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        log.warning("source_run_failed", extra={"source": key, "error": error})

    with system_db_sync() as conn:
        conn.execute(
            "update public.source_runs set status = %s, error = %s, queries = %s, fetched = %s,"
            " new_items = %s, finished_at = now(),"
            " cost_usd = coalesce((select sum(cost_usd) from public.usage_events"
            "                      where run_id = %s), 0)"
            " where id = %s",
            (status, error, len(queries), seen, new, run_id, run_id),
        )
        conn.execute("update public.sources set last_run_at = now() where key = %s", (key,))
    result = {
        "source": key,
        "run_id": str(run_id),
        "status": status,
        "queries": len(queries),
        "fetched": seen,
        "new": new,
    }
    if error:
        result["error"] = error
    log.info("source_run_finished", extra=result)
    return result


def due_sources() -> list[str]:
    with system_db_sync() as conn:
        rows = conn.execute(
            "select key from public.sources"
            " where enabled and kind = 'pull' and schedule_seconds is not null"
            "   and (risk <> 'red' or red_override_at is not null)"
            "   and (last_run_at is null"
            "        or last_run_at + make_interval(secs => schedule_seconds) <= now())"
            " order by key"
        ).fetchall()
    return [r["key"] for r in rows]
