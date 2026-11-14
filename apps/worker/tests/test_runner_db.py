"""The run loop against the local database (run with `make test-db`)."""

from __future__ import annotations

import psycopg
import pytest

from core.settings import get_settings
from worker.ingest.runner import run_source

pytestmark = pytest.mark.db


def _admin() -> psycopg.Connection[tuple[object, ...]]:
    url = get_settings().database_url_admin
    assert url is not None
    return psycopg.connect(url.get_secret_value(), autocommit=True)


def test_same_run_twice_adds_nothing_the_second_time() -> None:
    with _admin() as conn:
        conn.execute("update public.sources set monthly_cap_usd = 100 where key = 'fake'")
    first = run_source("fake", "cli")
    second = run_source("fake", "cli")
    assert first["status"] == second["status"] == "succeeded"
    assert second["new"] == 0 and second["fetched"] == first["fetched"] > 0


def test_cap_stops_the_run_cleanly() -> None:
    with _admin() as conn:
        conn.execute("update public.sources set monthly_cap_usd = 0 where key = 'fake'")
    try:
        result = run_source("fake", "cli")
    finally:
        with _admin() as conn:
            conn.execute("update public.sources set monthly_cap_usd = 1 where key = 'fake'")
    assert result["status"] == "capped" and result["new"] == 0


def test_disabled_source_is_skipped_by_the_schedule() -> None:
    assert run_source("fake", "schedule")["status"] == "skipped"  # fake is disabled
