"""The same wall through Supabase's REST API with real tokens (terminal tests 1-4) and
through our own API (terminal tests 5-7)."""

from __future__ import annotations

import httpx
import psycopg
import pytest

from core.settings import get_settings
from tests.isolation.conftest import World


@pytest.fixture(scope="module")
def rest(world: World) -> httpx.Client:
    return httpx.Client(
        base_url=f"{world.env['SUPA']}/rest/v1", headers={"apikey": world.env["ANON"]}, timeout=15
    )


@pytest.fixture(scope="module")
def api(world: World) -> httpx.Client:
    client = httpx.Client(base_url=world.env["API"], timeout=15)
    try:
        client.get("/healthz").raise_for_status()
    except httpx.HTTPError:
        pytest.skip("API is not running (make up)")
    return client


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("table", ["tenants", "memberships", "invitations", "audit_log"])
def test_no_login_gets_no_rows(rest: httpx.Client, table: str) -> None:  # test 1
    res = rest.get(f"/{table}", params={"select": "*"})
    assert res.status_code == 401 or res.json() == []


def test_a_cannot_read_b_memberships(rest: httpx.Client, world: World) -> None:  # test 2
    res = rest.get(
        "/memberships",
        params={"tenant_id": f"eq.{world.tenant_b}", "select": "*"},
        headers=_bearer(world.env["JWT_A"]),
    )
    assert res.status_code == 200 and res.json() == []


def test_a_sees_only_own_company(rest: httpx.Client, world: World) -> None:
    res = rest.get("/tenants", params={"select": "id"}, headers=_bearer(world.env["JWT_A"]))
    assert res.status_code == 200
    assert {row["id"] for row in res.json()} == {world.tenant_a}


def test_a_cannot_write_into_b(rest: httpx.Client, world: World) -> None:  # test 3
    res = rest.post(
        "/invitations",
        headers=_bearer(world.env["JWT_A"]),
        json={"tenant_id": world.tenant_b, "email": "x@example.com", "role": "admin"},
    )
    assert res.status_code in (401, 403)
    assert res.json().get("code") == "42501"


def test_member_cannot_promote_self(rest: httpx.Client, world: World) -> None:  # test 4
    res = rest.patch(
        "/memberships",
        params={"user_id": f"eq.{world.member_a}"},
        headers={**_bearer(world.env["JWT_MEMBER_A"]), "Prefer": "return=representation"},
        json={"role": "owner"},
    )
    assert res.status_code == 200 and res.json() == []


def test_tampered_token_is_rejected(api: httpx.Client, world: World) -> None:  # test 5
    assert api.get("/me", headers=_bearer(world.env["JWT_A"] + "x")).status_code == 401


def test_wrong_company_header_is_refused(api: httpx.Client, world: World) -> None:  # test 6
    res = api.get("/team", headers={**_bearer(world.env["JWT_A"]), "X-Tenant-Id": world.tenant_b})
    assert res.status_code == 403


def test_normal_user_on_admin_route(api: httpx.Client, world: World) -> None:  # test 7
    assert api.get("/admin/tenants", headers=_bearer(world.env["JWT_A"])).status_code == 403


def test_rest_refuses_a_revoked_session(rest: httpx.Client, world: World) -> None:
    """Sign-out everywhere must also stop direct REST calls, not only our API."""
    auth = f"{world.env['SUPA']}/auth/v1"

    def session() -> str:
        res = httpx.post(
            f"{auth}/token",
            params={"grant_type": "password"},
            headers={"apikey": world.env["ANON"]},
            json={"email": "owner-b@example.com", "password": world.env["TEST_PASSWORD"]},
            timeout=15,
        )
        res.raise_for_status()
        return str(res.json()["access_token"])

    first, second = session(), session()
    assert rest.get("/tenants", params={"select": "id"}, headers=_bearer(second)).status_code == 200
    httpx.post(
        f"{auth}/logout",
        params={"scope": "global"},
        headers={"apikey": world.env["ANON"], **_bearer(first)},
        timeout=15,
    ).raise_for_status()
    res = rest.get("/tenants", params={"select": "id"}, headers=_bearer(second))
    assert res.status_code == 401, res.text


def test_rest_role_change_is_audited(rest: httpx.Client, world: World) -> None:
    res = rest.patch(
        "/memberships",
        params={"tenant_id": f"eq.{world.tenant_a}", "user_id": f"eq.{world.member_a}"},
        headers={**_bearer(world.env["JWT_A"]), "Prefer": "return=representation"},
        json={"role": "admin"},
    )
    assert res.status_code == 200 and len(res.json()) == 1
    url = get_settings().database_url_admin
    assert url is not None
    with psycopg.connect(url.get_secret_value()) as conn:
        row = conn.execute(
            "select actor_user_id::text from public.audit_log"
            " where action = 'membership.role_changed' and target_id = %s"
            "   and occurred_at > now() - interval '1 minute' order by id desc limit 1",
            (world.member_a,),
        ).fetchone()
        conn.execute(  # put member A back for the other tests
            "update public.memberships set role = 'member' where tenant_id = %s and user_id = %s",
            (world.tenant_a, world.member_a),
        )
        conn.commit()
    assert row is not None and row[0] == world.owner_a


def test_platform_admin_with_mfa_can_read(api: httpx.Client, world: World) -> None:
    res = api.get(f"/admin/tenants/{world.tenant_b}", headers=_bearer(world.env["JWT_ADMIN"]))
    assert res.status_code == 200 and res.json()["id"] == world.tenant_b
