"""Query planner: merge every active company's compiled queries for one source.

Queries shared by many companies come first, duplicates are removed (case-insensitive),
and the result respects the source's budget of queries per run. One query run serves
every company that wants it: collection is shared, matching (module 5) is per company.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import psycopg
from psycopg.rows import DictRow

Conn = psycopg.Connection[DictRow]


def merge_queries(per_company: list[list[str]], budget: int) -> list[str]:
    """Pure function: most widely wanted queries first, ties in first-seen order."""
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    display: dict[str, str] = {}
    for queries in per_company:
        for q in dict.fromkeys(q.strip() for q in queries if q and q.strip()):
            key = " ".join(q.lower().split())
            counts[key] += 1
            first_seen.setdefault(key, len(first_seen))
            display.setdefault(key, q)
    ordered = sorted(counts, key=lambda k: (-counts[k], first_seen[k]))
    return [display[k] for k in ordered[:budget]]


def plan(conn: Conn, family: str, budget: int) -> list[str]:
    rows = conn.execute(
        "select c.search_terms -> 'sources' -> %s -> 'queries' as queries"
        " from public.tenant_profiles p"
        " join public.tenants t on t.id = p.tenant_id and t.status = 'active'"
        " join public.profile_compilations c"
        "   on c.tenant_id = p.tenant_id and c.profile_version = p.compiled_version"
        "  and c.status = 'ready'"
        " order by p.tenant_id",
        (family,),
    ).fetchall()
    per_company: list[list[str]] = [list(r["queries"] or []) for r in rows]
    return merge_queries(per_company, budget)


def describe(queries: list[str]) -> dict[str, Any]:
    return {"count": len(queries), "sample": queries[:5]}
