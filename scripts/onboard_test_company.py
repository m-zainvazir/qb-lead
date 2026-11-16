"""Test setup: Agency A finishes onboarding through the API, then waits for its compiled profile.

  uv run python scripts/onboard_test_company.py   (after `make seed-test`; the API must be up)

Used by scripts/m3_terminal_tests.sh so collection has search phrases to run with. It goes
through the same endpoints as the onboarding wizard (PUT /onboarding/progress, then
POST /onboarding/complete) and the worker compiles the profile. Idempotent: if the
profile is already compiled, it only reports that. Fake test data only.
"""

from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]


def load_test_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env.test.local").read_text(encoding="utf-8").splitlines():
        if line.startswith("export "):
            k, _, v = line[len("export ") :].partition("=")
            env[k] = shlex.split(v)[0]
    return env


def status(db_url: str, tenant: str) -> tuple[str | None, int]:
    with psycopg.connect(db_url, connect_timeout=15) as c:
        row = c.execute(
            "select p.compile_status,"
            " (select coalesce(jsonb_array_length("
            "    pc.search_terms -> 'sources' -> 'reddit' -> 'queries'), 0)"
            "    from public.profile_compilations pc where pc.tenant_id = p.tenant_id"
            "    and pc.status = 'ready' order by pc.profile_version desc limit 1)"
            " from public.tenant_profiles p where p.tenant_id = %s",
            (tenant,),
        ).fetchone()
    if row is None:
        return None, 0
    return row[0], int(row[1] or 0)


def main() -> int:
    env = load_test_env()
    tenant = env["TENANT_A"]
    current, phrases = status(env["DB_URL"], tenant)
    if current == "ready":
        print(f"Agency A profile already compiled ({phrases} short phrases)")
        return 0

    headers = {"Authorization": f"Bearer {env['JWT_A']}", "X-Tenant-Id": tenant}
    with httpx.Client(base_url=env["API"], headers=headers, timeout=30) as api:
        opts = api.get("/onboarding").raise_for_status().json()["options"]

        def ids(kind: str) -> list[str]:
            return [str(o["id"]) for o in opts[kind]]

        markets = [str(o["id"]) for o in opts["catalogue_markets"] if o["code"] in ("US", "GB")]
        answers: dict[str, Any] = {
            "business_type": "agency",
            "team_size": 5,
            "services": ids("catalogue_services"),
            "min_budget_usd": 1000,
            "client_sizes": ["small"],
            "markets": markets,
            "time_zone": "America/New_York",
            "signals": ids("catalogue_signals"),
            "tone": "professional",
            "priorities": ["quality"],
        }
        api.put(
            "/onboarding/progress", json={"current_step": 6, "answers": answers}
        ).raise_for_status()
        done = api.post("/onboarding/complete").raise_for_status().json()
        print(f"Agency A onboarding complete: profile version {done['version']}")

    deadline = time.monotonic() + 300  # the first compile may download the embedding model
    while time.monotonic() < deadline:
        current, phrases = status(env["DB_URL"], tenant)
        if current == "ready":
            print(f"Agency A profile compiled ({phrases} short phrases)")
            return 0
        if current == "failed":
            print("Agency A profile compile failed (see `make logs`)", file=sys.stderr)
            return 1
        time.sleep(3)
    print("Timed out waiting for the profile compile (is the worker running?)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
