# 0003 · Database access for public inbound routes (webhook, email)

- Status: accepted
- Date: 2026-11-14
- Module: 3

## Context

`POST /ingest/{token}` (a company's webhook) and `POST /inbound/email` (Mailgun deliveries) have no signed-in user, so `user_db()` (ADR 0001) cannot be used. `system_db()` bypasses RLS and is reserved for the worker and the admin module (CLAUDE.md). Widening it to the API's public routes would put a full-power connection behind an unauthenticated URL.

## Decision

A third, very narrow path: `ingest_db()` in `packages/core/core/db.py`.

- New role `ingest`: NOLOGIN, NOINHERIT, NOBYPASSRLS. `app_api` may `SET ROLE ingest` (granted `WITH INHERIT FALSE, SET TRUE`).
- `ingest` has **no table privileges**. It can only EXECUTE `private.ingest_webhook(...)` and `private.ingest_email(...)`.
- Those SECURITY DEFINER functions look up the endpoint by the SHA-256 of the token (or by the email local part), check that the endpoint is not revoked and the company is active, and insert exactly one private `raw_items` row for that company. The inner helper `private.insert_private_item` is not executable by `ingest`.
- In front of the database: the webhook token is checked for shape, rate limited per IP and per token hash (`WEBHOOK_RATE_PER_MINUTE`, default 60), and bodies are capped (512 KB). Email deliveries must carry a valid Mailgun HMAC signature (`MAILGUN_SIGNING_KEY`) no older than 5 minutes, are rejected if the token was seen before (replay), and attachments are refused.
- Unknown email addresses answer "accepted" (no probing); unknown webhook tokens answer 404.

## Consequences

- A bug in a public route can at worst add private raw items to a company whose secret the caller already knows.
- Token rotation is "create a new endpoint, revoke the old one"; tokens are shown once and only their hash is stored.
- Inbound email provider: Mailgun (it signs deliveries). Postmark and SendGrid inbound would need basic auth instead; switching means a new verifier in `api/routes/ingest.py`.
