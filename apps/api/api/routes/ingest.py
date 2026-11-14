"""Public inbound routes: a company's webhook and inbound email.

No user is signed in here. The database is reached only through `ingest_db()`, which can
call nothing but the private.ingest_* functions (docs/decisions/0003-inbound-path.md).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from api.email_parse import parse_email
from core import ratelimit
from core.db import ingest_db
from core.jobs import enqueue
from core.settings import get_settings

log = logging.getLogger(__name__)
router = APIRouter(tags=["inbound"])

Line = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class WebhookItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    body: str | None = Field(default=None, max_length=20000)
    url: str | None = Field(default=None, max_length=2000)
    author: Line | None = None
    external_id: Annotated[str, StringConstraints(max_length=200)] | None = None
    posted_at: datetime | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=20
    )

    @field_validator("url")
    @classmethod
    def web_links_only(cls, value: str | None) -> str | None:
        if value and not value.lower().startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/ingest/{token}", status_code=status.HTTP_202_ACCEPTED)
async def ingest_webhook(token: str, item: WebhookItem, request: Request) -> dict[str, Any]:
    if not await ratelimit.hit(f"ingest-ip:{_client_ip(request)}", 600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
    if not (20 <= len(token) <= 100) or not token.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown address")
    token_hash = _hash(token)
    if not await ratelimit.hit(f"ingest:{token_hash[:24]}", get_settings().webhook_rate_per_minute):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests for this address")

    async with ingest_db() as conn:
        row = await (
            await conn.execute(
                "select * from private.ingest_webhook(%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    token_hash,
                    item.external_id,
                    item.title,
                    item.body,
                    item.url,
                    item.author,
                    item.posted_at,
                    Jsonb({"metadata": item.metadata, "via": "webhook"}),
                ),
            )
        ).fetchone()
    raw_item_id = row["raw_item_id"] if row else None
    if raw_item_id and item.url:
        await enqueue("worker.tasks.enrich_raw_item", str(raw_item_id))
    return {"accepted": True, "duplicate": raw_item_id is None}


def _verify_mailgun(form: dict[str, str]) -> None:
    """Mailgun signs every delivery: HMAC-SHA256(signing key, timestamp + token)."""
    key = get_settings().mailgun_signing_key
    timestamp, token, signature = (
        form.get("timestamp", ""),
        form.get("token", ""),
        form.get("signature", ""),
    )
    if key is None or not (timestamp and token and signature) or not timestamp.isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid signature")
    if abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature too old")
    expected = hmac.new(
        key.get_secret_value().encode(), f"{timestamp}{token}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid signature")


@router.post("/inbound/email", status_code=status.HTTP_202_ACCEPTED)
async def inbound_email(request: Request) -> dict[str, Any]:
    if not await ratelimit.hit(f"email-ip:{_client_ip(request)}", 600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid signature")
    raw_form = await request.form(max_files=0, max_fields=200)  # attachments are refused
    form = {k: v for k, v in raw_form.items() if isinstance(v, str)}
    _verify_mailgun(form)
    if await ratelimit.seen_before(f"mailgun:{form['token']}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Replayed delivery")

    recipient = (form.get("recipient") or "").split(",")[0].strip().lower()
    local, _, domain = recipient.partition("@")
    if domain != get_settings().inbound_email_domain.lower():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown address")
    parsed = parse_email(
        form.get("sender", ""),
        form.get("subject", "")[:1000],
        form.get("stripped-text") or form.get("body-plain"),
        form.get("body-html"),
    )
    try:
        async with ingest_db() as conn:
            row = await (
                await conn.execute(
                    "select * from private.ingest_email(%s, %s, %s, %s, %s, %s, %s)",
                    (
                        local,
                        parsed.external_id or form.get("Message-Id"),
                        parsed.title,
                        parsed.body,
                        parsed.url,
                        None,
                        Jsonb({**parsed.payload, "via": "email"}),
                    ),
                )
            ).fetchone()
    except Exception as exc:
        if getattr(exc, "sqlstate", "") == "LG404":
            # Tell the provider "accepted" so unknown addresses cannot be probed.
            return {"accepted": True}
        raise
    raw_item_id = row["raw_item_id"] if row else None
    if raw_item_id and parsed.url:
        await enqueue("worker.tasks.enrich_raw_item", str(raw_item_id))
    return {"accepted": True}
