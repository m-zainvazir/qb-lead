"""Module 1 rules that are not plain cross-tenant reads."""

from __future__ import annotations

import hashlib
import secrets

import psycopg
import pytest
from psycopg.rows import DictRow

from core.settings import get_settings
from tests.isolation.conftest import World, act_as, as_owner, expect_sqlstate

Conn = psycopg.Connection[DictRow]


def test_member_cannot_promote_self(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.member_a))
    cur = conn.execute(
        "update public.memberships set role = 'owner' where user_id = %s", (world.member_a,)
    )
    assert cur.rowcount == 0


def test_owner_cannot_change_own_role(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    cur = conn.execute(
        "update public.memberships set role = 'member' where user_id = %s and tenant_id = %s",
        (world.owner_a, world.tenant_a),
    )
    assert cur.rowcount == 0


def test_owner_of_b_cannot_change_roles_in_a(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_b))
    cur = conn.execute(
        "update public.memberships set role = 'admin' where tenant_id = %s", (world.tenant_a,)
    )
    assert cur.rowcount == 0


def test_last_owner_cannot_be_removed(conn: Conn, world: World) -> None:
    as_owner(conn)
    with expect_sqlstate(conn, "LG409"):
        conn.execute(
            "delete from public.memberships where tenant_id = %s and role = 'owner'",
            (world.tenant_b,),
        )


def test_users_cannot_write_audit_log_directly(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    with expect_sqlstate(conn, "42501"):
        conn.execute(
            "insert into public.audit_log (actor_kind, action) values ('system', 'forged.entry')"
        )


def test_write_audit_refuses_other_tenant(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    with expect_sqlstate(conn, "42501"):
        conn.execute("select private.write_audit('test.forged', %s)", (world.tenant_b,))


@pytest.mark.parametrize("which", ["api", "system"])
def test_audit_log_is_append_only_for_app_roles(which: str) -> None:  # terminal test 10
    s = get_settings()
    url = (s.database_url_api if which == "api" else s.database_url_system).get_secret_value()
    role = "authenticated" if which == "api" else "service_role"
    with psycopg.connect(url) as c:
        for stmt in ("delete from public.audit_log", "update public.audit_log set action = 'x.y'"):
            for switch in (None, f"set local role {role}"):
                with expect_sqlstate(c, "42501"):
                    if switch:
                        c.execute(switch)
                    c.execute(stmt)


def test_audit_log_append_only_even_for_owner(conn: Conn) -> None:
    as_owner(conn)
    with expect_sqlstate(conn, "42501"):
        conn.execute("delete from public.audit_log")


def test_invitation_is_single_use(conn: Conn, world: World) -> None:
    token = secrets.token_urlsafe(32)
    as_owner(conn)
    conn.execute(
        "insert into public.invitations (tenant_id, email, role, token_hash, invited_by)"
        " values (%s, 'member-a@example.com', 'member', %s, %s)",
        (world.tenant_b, hashlib.sha256(token.encode()).hexdigest(), world.owner_b),
    )
    act_as(conn, world.claims(world.member_a, "member-a@example.com"))
    tenant = conn.execute("select private.accept_invitation(%s) as t", (token,)).fetchone()
    assert tenant is not None and str(tenant["t"]) == world.tenant_b
    with expect_sqlstate(conn, "LG404"):
        conn.execute("select private.accept_invitation(%s)", (token,))


def test_invitation_is_tied_to_one_email(conn: Conn, world: World) -> None:
    token = secrets.token_urlsafe(32)
    as_owner(conn)
    conn.execute(
        "insert into public.invitations (tenant_id, email, role, token_hash, invited_by)"
        " values (%s, 'someone-else@example.com', 'member', %s, %s)",
        (world.tenant_b, hashlib.sha256(token.encode()).hexdigest(), world.owner_b),
    )
    act_as(conn, world.claims(world.member_a, "member-a@example.com"))
    with expect_sqlstate(conn, "LG404"):
        conn.execute("select private.accept_invitation(%s)", (token,))


def test_expired_invitation_is_refused(conn: Conn, world: World) -> None:
    token = secrets.token_urlsafe(32)
    as_owner(conn)
    conn.execute(
        "insert into public.invitations"
        " (tenant_id, email, role, token_hash, invited_by, created_at, expires_at)"
        " values (%s, 'member-a@example.com', 'member', %s, %s,"
        "         now() - interval '8 days', now() - interval '1 day')",
        (world.tenant_b, hashlib.sha256(token.encode()).hexdigest(), world.owner_b),
    )
    act_as(conn, world.claims(world.member_a, "member-a@example.com"))
    with expect_sqlstate(conn, "LG404"):
        conn.execute("select private.accept_invitation(%s)", (token,))


def test_admin_cannot_invite_admins(conn: Conn, world: World) -> None:
    as_owner(conn)
    conn.execute(
        "update public.memberships set role = 'admin' where tenant_id = %s and user_id = %s",
        (world.tenant_a, world.member_a),
    )
    act_as(conn, world.claims(world.member_a))
    with expect_sqlstate(conn, "42501"):
        conn.execute(
            "insert into public.invitations (tenant_id, email, role, token_hash)"
            " values (%s, 'new-admin@example.com', 'admin', %s)",
            (world.tenant_a, hashlib.sha256(b"x").hexdigest()),
        )


def test_users_cannot_flip_internal_or_status(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    for column in ("is_internal", "status"):
        with expect_sqlstate(conn, "42501"):
            conn.execute(
                f"update public.tenants set {column} = {column} where id = %s",
                (world.tenant_a,),
            )


def test_suspended_company_is_invisible_to_members(conn: Conn, world: World) -> None:
    as_owner(conn)
    conn.execute("update public.tenants set status = 'suspended' where id = %s", (world.tenant_a,))
    act_as(conn, world.claims(world.owner_a))
    rows = conn.execute("select id from public.tenants where id = %s", (world.tenant_a,)).fetchall()
    assert rows == []


def test_platform_admin_check_needs_mfa(conn: Conn, world: World) -> None:
    act_as(conn, {**world.claims(world.admin), "aal": "aal1"})
    assert conn.execute("select private.is_platform_admin() as a").fetchone() == {"a": False}
    act_as(conn, {**world.claims(world.admin), "aal": "aal2"})
    assert conn.execute("select private.is_platform_admin() as a").fetchone() == {"a": True}
    act_as(conn, {**world.claims(world.owner_a), "aal": "aal2"})
    assert conn.execute("select private.is_platform_admin() as a").fetchone() == {"a": False}


def test_users_cannot_make_themselves_platform_admin(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    with expect_sqlstate(conn, "42501"):
        conn.execute(
            "insert into public.platform_admins (user_id, level) values (%s, 'super')",
            (world.owner_a,),
        )
