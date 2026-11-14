"""`python -m api.cli seed-test`: two test agencies with fake data on the LOCAL stack.

Creates (idempotently):
  * Agency A: owner-a@example.com (owner), member-a@example.com (member)
  * Agency B: owner-b@example.com (owner)
  * platform-admin@example.com in platform_admins, with TOTP enrolled so its token is aal2
and writes `.env.test.local` with the placeholders the module plans use
($API, $SUPA, $ANON, $JWT_A, $JWT_B, $JWT_MEMBER_A, $JWT_ADMIN, $TENANT_A, $TENANT_B, ...).

Refuses to run unless Supabase is on 127.0.0.1/localhost and APP_ENV is not production.
Tokens last 15 minutes; run it again for fresh ones.
"""

from __future__ import annotations

import secrets
import shlex
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import psycopg

from core.settings import get_settings, refuse_in_production

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / ".env.test.local"
NS = uuid.UUID("6f1c2b1e-6a43-4c55-9a3e-6d1f0f5c0b11")
TENANT_A = uuid.uuid5(NS, "agency-a")
TENANT_B = uuid.uuid5(NS, "agency-b")
USERS = {
    "owner_a": "owner-a@example.com",
    "member_a": "member-a@example.com",
    "owner_b": "owner-b@example.com",
    "admin": "platform-admin@example.com",
}


class SeedError(RuntimeError):
    pass


def _local_only() -> None:
    refuse_in_production("seed test data")
    host = urlparse(get_settings().supabase_url).hostname
    if host not in ("127.0.0.1", "localhost"):
        raise SeedError(f"seed-test only runs against a local Supabase (got {host})")


class Auth:
    def __init__(self) -> None:
        s = get_settings()
        if s.supabase_service_role_key is None:
            raise SeedError("SUPABASE_SERVICE_ROLE_KEY is required for seed-test")
        self.base = s.supabase_url.rstrip("/") + "/auth/v1"
        self.anon = s.supabase_anon_key.get_secret_value()
        self.service = s.supabase_service_role_key.get_secret_value()
        self.http = httpx.Client(timeout=15)

    def _admin(self) -> dict[str, str]:
        return {"apikey": self.service, "Authorization": f"Bearer {self.service}"}

    def ensure_user(self, email: str, password: str) -> str:
        res = self.http.get(
            f"{self.base}/admin/users", headers=self._admin(), params={"per_page": 1000}
        )
        res.raise_for_status()
        for user in res.json().get("users", []):
            if user["email"] == email:
                upd = self.http.put(
                    f"{self.base}/admin/users/{user['id']}",
                    headers=self._admin(),
                    json={"password": password, "email_confirm": True},
                )
                upd.raise_for_status()
                return str(user["id"])
        created = self.http.post(
            f"{self.base}/admin/users",
            headers=self._admin(),
            json={"email": email, "password": password, "email_confirm": True},
        )
        created.raise_for_status()
        return str(created.json()["id"])

    def sign_in(self, email: str, password: str) -> str:
        res = self.http.post(
            f"{self.base}/token",
            params={"grant_type": "password"},
            headers={"apikey": self.anon},
            json={"email": email, "password": password},
        )
        res.raise_for_status()
        return str(res.json()["access_token"])

    def aal2_token(self, user_id: str, token: str) -> str:
        """Re-enroll a TOTP factor and verify it, returning an aal2 access token."""
        import pyotp

        user = self.http.get(f"{self.base}/admin/users/{user_id}", headers=self._admin())
        user.raise_for_status()
        for old in user.json().get("factors") or []:
            self.http.delete(
                f"{self.base}/admin/users/{user_id}/factors/{old['id']}", headers=self._admin()
            ).raise_for_status()
        headers = {"apikey": self.anon, "Authorization": f"Bearer {token}"}
        enroll = self.http.post(
            f"{self.base}/factors",
            headers=headers,
            json={"factor_type": "totp", "friendly_name": f"seed-{int(time.time())}"},
        )
        enroll.raise_for_status()
        factor: dict[str, Any] = enroll.json()
        challenge = self.http.post(f"{self.base}/factors/{factor['id']}/challenge", headers=headers)
        challenge.raise_for_status()
        verify = self.http.post(
            f"{self.base}/factors/{factor['id']}/verify",
            headers=headers,
            json={
                "challenge_id": challenge.json()["id"],
                "code": pyotp.TOTP(factor["totp"]["secret"]).now(),
            },
        )
        verify.raise_for_status()
        return str(verify.json()["access_token"])


def _seed_db(ids: dict[str, str]) -> None:
    url = get_settings().database_url_admin
    if url is None:
        raise SeedError("DATABASE_URL_ADMIN is required for seed-test")
    with psycopg.connect(url.get_secret_value()) as conn, conn.transaction():
        conn.execute(
            "insert into public.tenants (id, name, type, created_by) values"
            " (%s, 'Agency A (test)', 'agency', %s), (%s, 'Agency B (test)', 'agency', %s)"
            " on conflict (id) do update set status = 'active'",
            (TENANT_A, ids["owner_a"], TENANT_B, ids["owner_b"]),
        )
        conn.execute(
            "insert into public.memberships (tenant_id, user_id, role) values"
            " (%s, %s, 'owner'), (%s, %s, 'member'), (%s, %s, 'owner')"
            " on conflict (tenant_id, user_id) do nothing",
            (TENANT_A, ids["owner_a"], TENANT_A, ids["member_a"], TENANT_B, ids["owner_b"]),
        )
        # A previous test run may have promoted member A; put the role back.
        conn.execute(
            "update public.memberships set role = 'member' where tenant_id = %s and user_id = %s",
            (TENANT_A, ids["member_a"]),
        )
        conn.execute(
            "insert into public.platform_admins (user_id, level) values (%s, 'super')"
            " on conflict (user_id) do nothing",
            (ids["admin"],),
        )


def _seed_inbound() -> tuple[str, str]:
    """A fresh webhook token for Agency A (older seed tokens revoked) and a fixed email address."""
    url = get_settings().database_url_admin
    assert url is not None
    token = secrets.token_urlsafe(32)
    with psycopg.connect(url.get_secret_value()) as conn, conn.transaction():
        conn.execute(
            "update public.inbound_endpoints set revoked_at = now()"
            " where tenant_id = %s and token_hint like 'seed%%' and revoked_at is null",
            (TENANT_A,),
        )
        conn.execute(
            "insert into public.inbound_endpoints (tenant_id, kind, token_hash, token_hint)"
            " values (%s, 'webhook', encode(extensions.digest(%s, 'sha256'), 'hex'), 'seed')",
            (TENANT_A, token),
        )
        conn.execute(
            "insert into public.inbound_endpoints (tenant_id, kind, token_hash, token_hint,"
            " email_local) values (%s, 'email', encode(extensions.digest(%s, 'sha256'), 'hex'),"
            " 'seedml', 'in-seed-agency-a') on conflict (email_local) do nothing",
            (TENANT_A, secrets.token_urlsafe(32)),
        )
    return token, f"in-seed-agency-a@{get_settings().inbound_email_domain}"


def run() -> int:
    _local_only()
    s = get_settings()
    auth = Auth()
    password = "Seed-" + secrets.token_urlsafe(18) + "9a"
    ids = {key: auth.ensure_user(email, password) for key, email in USERS.items()}
    _seed_db(ids)
    tokens = {key: auth.sign_in(email, password) for key, email in USERS.items()}
    tokens["admin"] = auth.aal2_token(ids["admin"], tokens["admin"])

    token_a, email_a = _seed_inbound()
    assert s.database_url_admin is not None and s.supabase_service_role_key is not None
    values = {
        "API": "http://localhost:8000",
        "SUPA": s.supabase_url.rstrip("/"),
        "ANON": s.supabase_anon_key.get_secret_value(),
        "JWT_A": tokens["owner_a"],
        "JWT_B": tokens["owner_b"],
        "JWT_MEMBER_A": tokens["member_a"],
        "JWT_ADMIN": tokens["admin"],
        "TENANT_A": str(TENANT_A),
        "TENANT_B": str(TENANT_B),
        "USER_OWNER_A": ids["owner_a"],
        "USER_MEMBER_A": ids["member_a"],
        "USER_OWNER_B": ids["owner_b"],
        "USER_ADMIN": ids["admin"],
        "TEST_PASSWORD": password,
        "TOKEN_A": token_a,
        "INBOUND_EMAIL_A": email_a,
        "DB_URL": s.database_url_admin.get_secret_value(),
        "APP_DB_URL": s.database_url_api.get_secret_value(),
        "SUPABASE_SERVICE_ROLE_KEY": s.supabase_service_role_key.get_secret_value(),
    }
    lines = [
        "# Written by `python -m api.cli seed-test`. LOCAL fake data only; tokens last 15 minutes.",
        *(f"export {k}={shlex.quote(v)}" for k, v in values.items()),
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"seeded Agency A {TENANT_A} and Agency B {TENANT_B}; wrote {OUT.name}")
    return 0
