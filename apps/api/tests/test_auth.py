"""JWT verification rules (no database needed)."""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
import pytest
from fastapi import HTTPException

from api.auth import verify_token
from core.settings import get_settings

SECRET = "unit-test-secret-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def _hs_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _token(**overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "sub": str(uuid.uuid4()),
        "aud": "authenticated",
        "iss": "http://127.0.0.1:54321/auth/v1",
        "role": "authenticated",
        "iat": now,
        "exp": now + 600,
        "email": "a@example.com",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, SECRET, algorithm="HS256")


async def test_valid_token_passes() -> None:
    claims = await verify_token(_token())
    assert claims["role"] == "authenticated"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 60},  # expired
        {"aud": "something-else"},  # wrong audience
        {"iss": "https://evil.example.com/auth/v1"},  # wrong issuer
        {"role": "service_role"},  # service key
        {"role": "anon"},  # anon key
        {"aud": None},  # Supabase anon/service keys carry no aud
        {"sub": "not-a-uuid"},
    ],
)
async def test_bad_claims_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_token(_token(**overrides))
    assert exc.value.status_code == 401


async def test_tampered_signature_is_rejected() -> None:
    with pytest.raises(HTTPException):
        await verify_token(_token() + "x")


async def test_alg_none_is_rejected() -> None:
    unsigned = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "authenticated"}, None, algorithm="none"
    )
    with pytest.raises(HTTPException):
        await verify_token(unsigned)


async def test_other_secret_is_rejected() -> None:
    forged = jwt.encode(
        jwt.decode(_token(), options={"verify_signature": False}),
        "another-secret-that-is-also-long-enough!!",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        await verify_token(forged)
