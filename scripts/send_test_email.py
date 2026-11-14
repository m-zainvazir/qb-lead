"""Send a signed fake Mailgun delivery to the local API (LOCAL ONLY).

    uv run python scripts/send_test_email.py in-seed-agency-a@in.leadgen.local [--upwork]

Signs with MAILGUN_SIGNING_KEY from .env exactly as Mailgun does, so the real
verification path is exercised. Never point this at staging or production.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import secrets
import sys
import time

import httpx

sys.path.insert(0, "packages/core")
from core.settings import get_settings

UPWORK = """New job matching your saved search

Build an AI voice agent for appointment booking
Fixed-price - Budget: $1,500
We need a Vapi or Retell agent that books appointments for a dental clinic.
View job: https://www.upwork.com/jobs/~021234567890abcdef
"""
GENERAL = "Hi, we need a new website for our bakery. See https://example.com for the current one."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipient")
    parser.add_argument("--upwork", action="store_true")
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    if "localhost" not in args.api and "127.0.0.1" not in args.api:
        sys.exit("Refusing: local API only")
    s = get_settings()
    if s.mailgun_signing_key is None:
        sys.exit("MAILGUN_SIGNING_KEY is not set (run: uv run python scripts/make_env.py --merge)")
    ts, token = str(int(time.time())), secrets.token_hex(25)
    signature = hmac.new(
        s.mailgun_signing_key.get_secret_value().encode(), f"{ts}{token}".encode(), hashlib.sha256
    ).hexdigest()
    data = {
        "recipient": args.recipient,
        "sender": "Upwork <donotreply@upwork.com>" if args.upwork else "owner@example.com",
        "subject": "New job: Build an AI voice agent - Upwork" if args.upwork else "Website help",
        "body-plain": UPWORK if args.upwork else GENERAL,
        "Message-Id": f"<{secrets.token_hex(8)}@example.com>",
        "timestamp": ts,
        "token": token,
        "signature": signature,
    }
    res = httpx.post(f"{args.api}/inbound/email", data=data, timeout=15)
    print(res.status_code, res.text)
    return 0 if res.status_code == 202 else 1


if __name__ == "__main__":
    sys.exit(main())
