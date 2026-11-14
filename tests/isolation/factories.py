"""One factory per tenant table. A table with `tenant_id` and no factory FAILS the suite.

A factory inserts one row for a tenant (as the database owner, bypassing RLS) and
returns `insert_values`: a complete, valid row a user would try to write into
another tenant. Add a factory in the same commit as the table's migration.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from typing import Any

import psycopg
from psycopg.rows import DictRow

Conn = psycopg.Connection[DictRow]
Factory = Callable[[Conn, str, dict[str, str]], dict[str, Any]]

# How each table names its tenant column (tenants is keyed by id).
TENANT_COLUMN: dict[str, str] = {"tenants": "id"}


def _token_hash() -> str:
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def tenants(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    # The seeded tenant row already exists; a user must never be able to create one directly.
    return {"name": "Injected", "type": "agency"}


def memberships(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.memberships (tenant_id, user_id, role) values (%s, %s, 'member')"
        " on conflict do nothing",
        (tenant_id, users["admin"]),
    )
    return {"tenant_id": tenant_id, "user_id": users["owner_a"], "role": "owner"}


def invitations(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.invitations (tenant_id, email, role, token_hash, invited_by)"
        " values (%s, %s, 'member', %s, %s)",
        (tenant_id, f"iso-{secrets.token_hex(4)}@example.com", _token_hash(), users["owner"]),
    )
    return {
        "tenant_id": tenant_id,
        "email": f"iso-{secrets.token_hex(4)}@example.com",
        "role": "member",
        "token_hash": _token_hash(),
    }


def audit_log(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.audit_log (actor_kind, tenant_id, action) values ('system', %s, %s)",
        (tenant_id, "isolation.seeded"),
    )
    return {"actor_kind": "user", "tenant_id": tenant_id, "action": "forged.entry"}


# --- module 2 -------------------------------------------------------------------------
ZERO_VECTOR = "[" + ",".join(["0.01"] * 384) + "]"


def _id(conn: Conn, table: str, column: str, value: str) -> str:
    row = conn.execute(f"select id from public.{table} where {column} = %s", (value,)).fetchone()
    assert row is not None, f"seed row {table}.{column}={value} missing"
    return str(row["id"])


def tenant_profiles(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.tenant_profiles (tenant_id, type, tone) values (%s, 'agency', 'direct')"
        " on conflict (tenant_id) do nothing",
        (tenant_id,),
    )
    return {"tenant_id": tenant_id, "type": "freelancer"}


def tenant_services(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.tenant_services (tenant_id, service_id) values (%s, %s)"
        " on conflict do nothing",
        (tenant_id, _id(conn, "services", "slug", "ai-automation")),
    )
    return {"tenant_id": tenant_id, "custom_name": f"Injected {secrets.token_hex(3)}"}


def tenant_markets(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.tenant_markets (tenant_id, market_id) values (%s, %s)"
        " on conflict do nothing",
        (tenant_id, _id(conn, "markets", "code", "US")),
    )
    return {"tenant_id": tenant_id, "market_id": _id(conn, "markets", "code", "PT")}


def tenant_signals(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.tenant_signals (tenant_id, signal_type_id) values (%s, %s)"
        " on conflict do nothing",
        (tenant_id, _id(conn, "signal_types", "key", "job_post")),
    )
    return {
        "tenant_id": tenant_id,
        "signal_type_id": _id(conn, "signal_types", "key", "growth_event"),
    }


def tenant_exclusions(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.tenant_exclusions (tenant_id, value) values (%s, 'gambling')",
        (tenant_id,),
    )
    return {"tenant_id": tenant_id, "kind": "keyword", "value": "injected"}


def onboarding_progress(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.onboarding_progress (tenant_id, current_step) values (%s, 2)"
        " on conflict (tenant_id) do nothing",
        (tenant_id,),
    )
    return {"tenant_id": tenant_id, "current_step": 1, "answers": "{}"}


def profile_compilations(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.profile_compilations (tenant_id, profile_version, status)"
        " values (%s, 9000 + floor(random() * 999)::int, 'ready') on conflict do nothing",
        (tenant_id,),
    )
    return {"tenant_id": tenant_id, "profile_version": 1, "status": "ready"}


def _tenant_service(conn: Conn, tenant_id: str) -> str:
    row = conn.execute(
        "insert into public.tenant_services (tenant_id, custom_name) values (%s, %s) returning id",
        (tenant_id, f"Fingerprinted {secrets.token_hex(3)}"),
    ).fetchone()
    assert row is not None
    return str(row["id"])


def service_fingerprints(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    service = _tenant_service(conn, tenant_id)
    conn.execute(
        "insert into public.service_fingerprints (tenant_id, tenant_service_id, profile_version,"
        " embedding_model, dims, embedding, source_text) values (%s, %s, 1, 'test', 384, %s, 'x')",
        (tenant_id, service, ZERO_VECTOR),
    )
    return {
        "tenant_id": tenant_id,
        "tenant_service_id": service,
        "profile_version": 2,
        "embedding_model": "test",
        "dims": 384,
        "embedding": ZERO_VECTOR,
        "source_text": "injected",
    }


def portfolio_items(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.portfolio_items (tenant_id, title, file_path, mime_type, size_bytes)"
        " values (%s, 'Case study', %s, 'application/pdf', 1000)",
        (tenant_id, f"{tenant_id}/{secrets.token_hex(8)}.pdf"),
    )
    return {
        "tenant_id": tenant_id,
        "title": "Injected",
        "file_path": f"{tenant_id}/{secrets.token_hex(8)}.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 10,
    }


def usage_events(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.usage_events (tenant_id, provider, operation, units, unit)"
        " values (%s, 'test', 'isolation.seed', 1, 'call')",
        (tenant_id,),
    )
    return {"tenant_id": tenant_id, "provider": "forged", "operation": "x", "cost_usd": 0}


# --- module 3 -------------------------------------------------------------------------
def raw_items(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.raw_items (source_key, external_id, visibility, tenant_id, title, body)"
        " values ('webhook', %s, 'private', %s, 'Private lead', 'body')",
        (f"iso-{secrets.token_hex(6)}", tenant_id),
    )
    conn.execute(  # a pooled row too: no customer may ever read it
        "insert into public.raw_items (source_key, external_id, visibility, title)"
        " values ('hackernews', %s, 'pooled', 'Pooled post')",
        (f"iso-{secrets.token_hex(6)}",),
    )
    return {
        "source_key": "webhook",
        "external_id": f"forged-{secrets.token_hex(4)}",
        "visibility": "private",
        "tenant_id": tenant_id,
        "title": "Forged",
    }


def tenant_sources(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.tenant_sources (tenant_id, source_key) values (%s, 'hackernews')"
        " on conflict do nothing",
        (tenant_id,),
    )
    return {"tenant_id": tenant_id, "source_key": "web_exa"}


def inbound_endpoints(conn: Conn, tenant_id: str, users: dict[str, str]) -> dict[str, Any]:
    conn.execute(
        "insert into public.inbound_endpoints (tenant_id, kind, token_hash, token_hint)"
        " values (%s, 'webhook', %s, 'abcd')",
        (tenant_id, _token_hash()),
    )
    return {
        "tenant_id": tenant_id,
        "kind": "webhook",
        "token_hash": _token_hash(),
        "token_hint": "abcd",
    }


FACTORIES: dict[str, Factory] = {
    "tenants": tenants,
    "memberships": memberships,
    "invitations": invitations,
    "audit_log": audit_log,
    "tenant_profiles": tenant_profiles,
    "tenant_services": tenant_services,
    "tenant_markets": tenant_markets,
    "tenant_signals": tenant_signals,
    "tenant_exclusions": tenant_exclusions,
    "onboarding_progress": onboarding_progress,
    "profile_compilations": profile_compilations,
    "service_fingerprints": service_fingerprints,
    "portfolio_items": portfolio_items,
    "usage_events": usage_events,
    "raw_items": raw_items,
    "tenant_sources": tenant_sources,
    "inbound_endpoints": inbound_endpoints,
}
