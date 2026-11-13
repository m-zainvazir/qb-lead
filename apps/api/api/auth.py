"""Login dependency: verify the Supabase JWT, check the session, attach tenant and role.

* Signature: ES256/RS256 keys from the Supabase JWKS (cached), or HS256 with the
  project secret when the token has no `kid` known to the JWKS (local fallback).
* Claims: `exp`, `aud` (= authenticated), `iss` (= <supabase>/auth/v1), `sub`, and
  `role` must be `authenticated` (anon and service-role keys are refused).
* Session: the token's session must still exist (sign-out everywhere and password
  reset end it at once, not when the 15-minute token expires).
* Tenant: `X-Tenant-Id` is checked against `memberships` on every request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWK

from core.db import user_db
from core.logging import client_ip_var
from core.settings import get_settings

log = logging.getLogger(__name__)

Role = Literal["owner", "admin", "member"]
_ASYMMETRIC = {"ES256", "RS256", "EdDSA"}


class _Jwks:
    """Async JWKS cache. Refetches at most every 30 s when an unknown `kid` shows up."""

    def __init__(self) -> None:
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, kid: str) -> PyJWK | None:
        s = get_settings()
        stale = time.monotonic() - self._fetched_at > s.jwks_cache_seconds
        unknown_and_cool = kid not in self._keys and time.monotonic() - self._fetched_at > 30
        if stale or unknown_and_cool:
            await self._refresh()
        return self._keys.get(kid)

    async def _refresh(self) -> None:
        async with self._lock:
            url = f"{get_settings().supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    res = await client.get(url)
                    res.raise_for_status()
                keys = {}
                for jwk in res.json().get("keys", []):
                    if jwk.get("kid") and jwk.get("alg") in _ASYMMETRIC:
                        keys[jwk["kid"]] = PyJWK(jwk)
                self._keys = keys
            except (httpx.HTTPError, ValueError, jwt.PyJWKError):
                log.warning("jwks_refresh_failed", exc_info=True)
            finally:
                self._fetched_at = time.monotonic()


jwks = _Jwks()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc
    alg, kid = header.get("alg"), header.get("kid")

    key: Any
    if alg in _ASYMMETRIC and kid:
        jwk = await jwks.get(kid)
        if jwk is None or jwk.algorithm_name != alg:
            raise _unauthorized()
        key = jwk.key
    elif alg == "HS256" and s.supabase_jwt_secret is not None:
        key = s.supabase_jwt_secret.get_secret_value()
    else:  # includes alg "none" and anything unexpected
        raise _unauthorized()

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=s.jwt_audience,
            issuer=s.jwt_issuer,
            leeway=10,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc
    if claims.get("role") != "authenticated":
        raise _unauthorized()
    try:
        UUID(str(claims["sub"]))
    except ValueError as exc:
        raise _unauthorized() from exc
    return claims


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    email: str
    claims: dict[str, Any]

    @property
    def aal(self) -> str:
        return str(self.claims.get("aal", "aal1"))


@dataclass(frozen=True)
class TenantContext:
    auth: AuthContext
    tenant_id: UUID
    role: Role

    @property
    def claims(self) -> dict[str, Any]:
        return self.auth.claims

    def require_role(self, *roles: Role) -> None:
        if self.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for your role")


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 8192:
        raise _unauthorized()
    return token.strip()


def _remember_client_ip(request: Request) -> None:
    # Behind a reverse proxy, uvicorn's --proxy-headers sets request.client from X-Forwarded-For.
    if request.client:
        client_ip_var.set(request.client.host)


async def current_user(request: Request) -> AuthContext:
    _remember_client_ip(request)
    claims = await verify_token(_bearer(request))
    async with user_db(claims) as conn:
        row = await (await conn.execute("select private.session_is_active() as active")).fetchone()
    if not row or not row["active"]:
        raise _unauthorized()
    request.state.user_id = claims["sub"]
    return AuthContext(
        user_id=UUID(claims["sub"]), email=str(claims.get("email", "")), claims=claims
    )


CurrentUser = Annotated[AuthContext, Depends(current_user)]


async def current_tenant(
    request: Request,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> TenantContext:
    """The signed-in user plus the company named in X-Tenant-Id, checked on the server.

    Without the header, a user who belongs to exactly one company acts in that company
    (CLI and simple clients); anyone with several companies must name one.
    """
    _remember_client_ip(request)
    claims = await verify_token(_bearer(request))
    tenant_id: UUID | None = None
    if x_tenant_id:
        try:
            tenant_id = UUID(x_tenant_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Tenant-Id is not valid") from exc

    async with user_db(claims) as conn:
        if tenant_id is None:
            only = await (
                await conn.execute(
                    "select array_agg(m.tenant_id) as ids from public.memberships m"
                    " join public.tenants t on t.id = m.tenant_id"
                    " where m.user_id = auth.uid() and t.status = 'active'"
                )
            ).fetchone()
            ids = (only or {}).get("ids") or []
            if len(ids) != 1:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Tenant-Id header is required")
            tenant_id = ids[0]
        row = await (
            await conn.execute(
                "select private.session_is_active() as active,"
                " (select m.role from public.memberships m"
                "   where m.tenant_id = %s and m.user_id = auth.uid()) as role",
                (tenant_id,),
            )
        ).fetchone()
    if not row or not row["active"]:
        raise _unauthorized()
    if row["role"] is None:  # not a member, or the company is suspended
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this company")
    request.state.user_id = claims["sub"]
    request.state.tenant_id = str(tenant_id)
    auth = AuthContext(
        user_id=UUID(claims["sub"]), email=str(claims.get("email", "")), claims=claims
    )
    return TenantContext(auth=auth, tenant_id=tenant_id, role=row["role"])


CurrentTenant = Annotated[TenantContext, Depends(current_tenant)]
