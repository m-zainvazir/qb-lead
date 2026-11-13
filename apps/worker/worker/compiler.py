"""Profile compiler: profile version -> search terms per source + a fingerprint per service.

Runs in the worker. Safe to run twice: a version that is already compiled is skipped,
two runs for the same company are serialised with an advisory lock, and outputs are
keyed by (company, version).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from core.db import system_db_sync
from core.embeddings import get_embedder, to_pgvector
from core.metering import metered_call
from core.settings import get_settings

log = logging.getLogger(__name__)
Conn = psycopg.Connection[DictRow]

SOURCES = ("reddit", "web_search", "job_boards")
MAX_PHRASES_PER_SERVICE = 40
MAX_QUERIES_PER_SOURCE = 60


def _quote(term: str) -> str:
    return '"' + term.replace('"', "") + '"'


def build_search_terms(profile: dict[str, Any], services: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure function: named profile fields in, search terms per source out.

    `services` items: {"name", "custom", "phrases": [...], "technologies": [...]}.
    Custom service names are used only as plain phrases (never parsed for meaning).
    """
    negatives = sorted({e.lower() for e in profile.get("exclusions", [])})
    per_service = []
    reddit: list[str] = []
    web: list[str] = []
    jobs: list[str] = []
    for svc in services:
        phrases = list(dict.fromkeys(p.strip().lower() for p in svc["phrases"] if p.strip()))
        phrases = phrases[:MAX_PHRASES_PER_SERVICE]
        techs = list(dict.fromkeys(svc["technologies"]))
        per_service.append(
            {
                "name": svc["name"],
                "custom": svc["custom"],
                "phrases": phrases,
                "technologies": techs,
            }
        )
        reddit.extend(phrases)
        for phrase in phrases[:10]:
            web.append(f'{_quote(phrase)} (hiring OR "looking for" OR recommend)')
        name = svc["name"].lower()
        jobs.extend([f"{name} freelancer", f"{name} agency", f"{name} contractor"])
        jobs.extend(f"{t.lower()} developer" for t in techs[:5])

    neg_suffix = "".join(f" -{_quote(n) if ' ' in n else n}" for n in negatives[:10])

    def finish(items: list[str], suffix: str = "") -> list[str]:
        return [q + suffix for q in list(dict.fromkeys(items))[:MAX_QUERIES_PER_SOURCE]]

    return {
        "services": per_service,
        "sources": {
            "reddit": {"queries": finish(reddit)},
            "web_search": {"queries": finish(web, neg_suffix)},
            "job_boards": {"queries": finish(jobs)},
        },
        "negative_keywords": negatives,
        "markets": profile.get("markets", []),
        "signals": profile.get("signals", {}),
        "min_budget_usd": profile.get("min_budget_usd"),
        "client_sizes": profile.get("client_sizes", []),
    }


def fingerprint_text(svc: dict[str, Any]) -> str:
    """The text a service's fingerprint is computed from (stored next to the vector)."""
    parts = [svc["name"]]
    if svc.get("description"):
        parts.append(svc["description"])
    parts.extend(svc.get("problems", []))
    parts.extend(svc["phrases"][:20])
    if svc["technologies"]:
        parts.append("Tools: " + ", ".join(svc["technologies"]))
    return ". ".join(parts)[:8000]


def _load(conn: Conn, tenant_id: UUID) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    profile = conn.execute(
        "select version, min_budget_usd, client_sizes from public.tenant_profiles"
        " where tenant_id = %s",
        (tenant_id,),
    ).fetchone()
    if profile is None:
        return None
    services = conn.execute(
        "select ts.id as tenant_service_id, coalesce(s.name, ts.custom_name) as name,"
        "  ts.custom_name is not null as custom, coalesce(s.description, '') as description,"
        "  coalesce((select array_agg(p.label order by p.sort_order) from public.problems p"
        "            where p.service_id = s.id and p.is_active), '{}') as problems,"
        "  coalesce((select array_agg(x order by p.sort_order) from public.problems p,"
        "            unnest(p.example_phrases) x where p.service_id = s.id and p.is_active), '{}')"
        "    as phrases,"
        "  coalesce((select array_agg(t.name order by t.name) from public.service_technologies st"
        "            join public.technologies t on t.id = st.technology_id"
        "            where st.service_id = s.id and t.is_active), '{}') as technologies"
        " from public.tenant_services ts left join public.services s on s.id = ts.service_id"
        " where ts.tenant_id = %s order by s.sort_order nulls last, name",
        (tenant_id,),
    ).fetchall()
    svc_list = []
    for row in services:
        svc = dict(row)
        if svc["custom"]:
            svc["phrases"] = [svc["name"]]
        svc["phrases"] = list(svc["phrases"]) + [p.lower() for p in svc["problems"]]
        svc_list.append(svc)
    markets = conn.execute(
        "select m.code, coalesce(tm.weight, m.default_weight)::float as weight"
        " from public.tenant_markets tm join public.markets m on m.id = tm.market_id"
        " where tm.tenant_id = %s and m.is_active order by m.sort_order",
        (tenant_id,),
    ).fetchall()
    signals = conn.execute(
        "select st.key, st.temperature, coalesce(ts.weight, st.default_weight)::float as weight"
        " from public.tenant_signals ts join public.signal_types st on st.id = ts.signal_type_id"
        " where ts.tenant_id = %s and st.is_active order by st.sort_order",
        (tenant_id,),
    ).fetchall()
    exclusions = conn.execute(
        "select value from public.tenant_exclusions where tenant_id = %s", (tenant_id,)
    ).fetchall()
    data = {
        "version": profile["version"],
        "min_budget_usd": profile["min_budget_usd"],
        "client_sizes": list(profile["client_sizes"]),
        "markets": [dict(m) for m in markets],
        "signals": {
            "hot": [dict(s) for s in signals if s["temperature"] == "hot"],
            "warm": [dict(s) for s in signals if s["temperature"] == "warm"],
        },
        "exclusions": [e["value"] for e in exclusions],
    }
    return data, svc_list


def compile_profile(tenant_id: UUID, *, force: bool = False) -> str:
    """Compile the company's current profile version. Returns what happened.

    `force` recompiles an already compiled version (used by `re-embed` after a model change).
    """
    embedder = get_embedder()
    with system_db_sync() as conn:
        conn.execute(
            "select pg_advisory_xact_lock(hashtextextended('compile:' || %s::text, 0))",
            (tenant_id,),
        )
        loaded = _load(conn, tenant_id)
        if loaded is None:
            return "no-profile"
        data, services = loaded
        version = int(data["version"])
        done = conn.execute(
            "select status from public.profile_compilations"
            " where tenant_id = %s and profile_version = %s",
            (tenant_id, version),
        ).fetchone()
        if done is not None and done["status"] == "ready" and not force:
            _mark_ready(conn, tenant_id, version)
            return "already-compiled"

        conn.execute(
            "insert into public.profile_compilations (tenant_id, profile_version, status)"
            " values (%s, %s, 'running')"
            " on conflict (tenant_id, profile_version) do update"
            " set status = 'running', error = null, started_at = now()",
            (tenant_id, version),
        )
        conn.execute(
            "update public.tenant_profiles set compile_status = 'compiling'"
            " where tenant_id = %s and version = %s",
            (tenant_id, version),
        )

        terms = build_search_terms(data, services)
        texts = [fingerprint_text(s) for s in services]
        chars = sum(len(t) for t in texts)
        vectors = (
            metered_call(
                lambda: embedder.embed(texts),
                provider=embedder.model,
                operation="embed.service_fingerprints",
                tenant_id=tenant_id,
                units=chars / 1000,
                unit="1k_chars",
                unit_cost_usd=get_settings().embedding_cost_per_1k_chars,
                metadata={"profile_version": version, "texts": len(texts)},
            )
            if texts
            else []
        )
        for svc, text, vector in zip(services, texts, vectors, strict=True):
            conn.execute(
                "insert into public.service_fingerprints (tenant_id, tenant_service_id,"
                " profile_version, embedding_model, dims, embedding, source_text)"
                " values (%s, %s, %s, %s, %s, %s::extensions.vector, %s)"
                " on conflict (tenant_service_id, profile_version, embedding_model) do update"
                " set embedding = excluded.embedding, source_text = excluded.source_text",
                (
                    tenant_id,
                    svc["tenant_service_id"],
                    version,
                    embedder.model,
                    embedder.dims,
                    to_pgvector(vector),
                    text,
                ),
            )
        cost = round(chars / 1000 * get_settings().embedding_cost_per_1k_chars, 6)
        conn.execute(
            "update public.profile_compilations set status = 'ready', search_terms = %s,"
            " embedding_model = %s, cost_usd = %s, finished_at = now()"
            " where tenant_id = %s and profile_version = %s",
            (Jsonb(terms), embedder.model, cost, tenant_id, version),
        )
        _mark_ready(conn, tenant_id, version)
    log.info("profile_compiled", extra={"tenant_id": str(tenant_id), "version": version})
    return "compiled"


def _mark_ready(conn: Conn, tenant_id: UUID, version: int) -> None:
    # Only if nobody saved a newer version meanwhile; otherwise it stays 'pending'.
    conn.execute(
        "update public.tenant_profiles set compile_status = 'ready', compiled_version = %s"
        " where tenant_id = %s and version = %s",
        (version, tenant_id, version),
    )


def mark_failed(tenant_id: UUID, error: str) -> None:
    """Record a failed compile for the current version (the failed run's rows rolled back)."""
    with system_db_sync() as conn:
        conn.execute(
            "insert into public.profile_compilations (tenant_id, profile_version, status, error,"
            " finished_at)"
            " select tenant_id, version, 'failed', %s, now() from public.tenant_profiles"
            " where tenant_id = %s"
            " on conflict (tenant_id, profile_version) do update"
            " set status = 'failed', error = excluded.error, finished_at = now()",
            (error[:2000], tenant_id),
        )
        conn.execute(
            "update public.tenant_profiles set compile_status = 'failed' where tenant_id = %s",
            (tenant_id,),
        )


def pending_tenants(limit: int = 50) -> list[UUID]:
    with system_db_sync() as conn:
        rows = conn.execute(
            "select tenant_id from public.tenant_profiles"
            " where compile_status = 'pending'"
            "    or (compile_status = 'compiling' and updated_at < now() - interval '10 minutes')"
            "    or (compile_status = 'failed' and updated_at < now() - interval '15 minutes')"
            " order by updated_at limit %s",
            (limit,),
        ).fetchall()
    return [r["tenant_id"] for r in rows]
