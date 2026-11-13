"""The API and the database must hash invitation tokens identically."""

from __future__ import annotations

import secrets

import psycopg
import pytest

from api.routes.invitations import hash_token
from core.settings import get_settings

pytestmark = pytest.mark.db


def test_python_and_sql_hashes_match() -> None:
    url = get_settings().database_url_admin
    assert url is not None
    token = secrets.token_urlsafe(32)
    with psycopg.connect(url.get_secret_value()) as conn:
        row = conn.execute("select private.hash_invitation_token(%s)", (token,)).fetchone()
    assert row is not None and row[0] == hash_token(token)
