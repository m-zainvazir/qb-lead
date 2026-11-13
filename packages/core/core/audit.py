"""Audit log writer: who did what, in which tenant, when.

* ``audit_as_user(conn, ...)``: inside ``user_db()``. Goes through
  ``private.write_audit``, which takes the actor from ``auth.uid()``, so it cannot be
  forged, and refuses tenants the user is not a member of.
* ``audit_as_system(conn, ...)``: inside ``system_db()`` (worker and admin module),
  where the caller names the actor explicitly.

Request id and client IP come from the transaction settings that ``core.db`` sets.
The table is append-only; there is no update or delete function on purpose.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from psycopg.types.json import Jsonb

from core.db import Conn


async def audit_as_user(
    conn: Conn,
    action: str,
    tenant_id: UUID | None,
    target_type: str | None = None,
    target_id: str | UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await conn.execute(
        "select private.write_audit(%s, %s, %s, %s, %s)",
        (
            action,
            tenant_id,
            target_type,
            str(target_id) if target_id is not None else None,
            Jsonb(metadata or {}),
        ),
    )


async def audit_as_system(
    conn: Conn,
    action: str,
    *,
    actor_kind: Literal["platform_admin", "system"],
    actor_user_id: UUID | None,
    tenant_id: UUID | None,
    target_type: str | None = None,
    target_id: str | UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await conn.execute(
        "insert into public.audit_log"
        " (actor_user_id, actor_kind, tenant_id, action, target_type, target_id, metadata,"
        "  request_id, ip)"
        " values (%s, %s, %s, %s, %s, %s, %s,"
        "  nullif(current_setting('app.request_id', true), ''),"
        "  nullif(current_setting('app.client_ip', true), '')::inet)",
        (
            actor_user_id,
            actor_kind,
            tenant_id,
            action,
            target_type,
            str(target_id) if target_id is not None else None,
            Jsonb(metadata or {}),
        ),
    )
