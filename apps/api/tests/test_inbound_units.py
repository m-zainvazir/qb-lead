import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException

from api.email_parse import parse_email
from api.routes.ingest import WebhookItem, _verify_mailgun
from core.settings import get_settings

UPWORK_TEXT = """New job matching your alert

Build an AI voice agent for appointment booking
Fixed-price - Budget: $1,500
We need a Vapi or Retell agent that books dental appointments.
View job: https://www.upwork.com/jobs/~021234567890abcdef
"""


def test_upwork_alert_is_parsed() -> None:
    p = parse_email(
        "Upwork <donotreply@upwork.com>",
        "Fwd: New job: Build an AI voice agent - Upwork",
        UPWORK_TEXT,
        None,
    )
    assert p.title == "Build an AI voice agent"
    assert p.payload["budget_usd"] == 1500.0
    assert p.url == "https://www.upwork.com/jobs/~021234567890abcdef"
    assert p.external_id == "upwork:~021234567890abcdef"


def test_general_email_uses_subject_text_and_first_link() -> None:
    p = parse_email(
        "someone@example.com",
        "Website help?",
        None,
        "<p>Hi, see <a href='https://shop.example.com'>https://shop.example.com</a></p><script>x</script>",
    )
    assert p.title == "Website help?"
    assert p.body == "Hi, see https://shop.example.com"  # tags and script content gone
    assert p.url == "https://shop.example.com"
    assert p.payload["parser"] == "general"


def test_webhook_rejects_unknown_fields_and_non_web_links() -> None:
    with pytest.raises(ValueError):
        WebhookItem.model_validate({"title": "x", "evil": 1})
    with pytest.raises(ValueError):
        WebhookItem.model_validate({"title": "x", "url": "file:///etc/passwd"})


def _signed(key: str, ts: int) -> dict[str, str]:
    token = "a" * 50
    sig = hmac.new(key.encode(), f"{ts}{token}".encode(), hashlib.sha256).hexdigest()
    return {"timestamp": str(ts), "token": token, "signature": sig}


def test_mailgun_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAILGUN_SIGNING_KEY", "test-signing-key")
    get_settings.cache_clear()
    try:
        _verify_mailgun(_signed("test-signing-key", int(time.time())))  # valid: no error
        for bad in (
            {},
            _signed("wrong-key", int(time.time())),
            _signed("test-signing-key", int(time.time()) - 3600),  # too old
        ):
            with pytest.raises(HTTPException) as exc:
                _verify_mailgun(bad)
            assert exc.value.status_code == 401
    finally:
        get_settings.cache_clear()
