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


FACTORIES: dict[str, Factory] = {
    "tenants": tenants,
    "memberships": memberships,
    "invitations": invitations,
    "audit_log": audit_log,
}
