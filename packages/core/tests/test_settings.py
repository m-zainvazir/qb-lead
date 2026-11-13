import pytest
from pydantic import ValidationError

from core.settings import Settings


def test_missing_required_setting_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_issuer_derived_from_url() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.jwt_issuer == "http://127.0.0.1:54321/auth/v1"


def test_secrets_not_in_repr() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert "anon-key" not in repr(s)
