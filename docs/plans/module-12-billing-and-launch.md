# 12 · Billing and launch readiness

## Goal

A stranger can sign up, pay, finish onboarding and get value without your help, and the product is safe and lawful to sell. This module ends with one full security pass over everything built so far.

## Decide first: who takes the payments

Stripe does not accept businesses registered in Pakistan (source: https://www.worldfirst.com/sasia/?p=52075, checked November 2026; confirm on Stripe's own country list). You have two routes:

| Route | What it means | Trade-off |
| --- | --- | --- |
| Merchant of record, such as Paddle or Lemon Squeezy | They are the legal seller, collect sales tax worldwide, and pay you out | Higher fee per sale, less control over checkout |
| A company in a Stripe-supported country | You use Stripe directly | Company setup and upkeep, and you handle sales tax yourself |

Either way, put billing behind one `BillingProvider` interface so the provider can change later.

## What gets built

- Billing: products and prices mapped to `plans`, a hosted checkout, a self-service portal for the customer, and webhooks that update the tenant's plan and status.
- `billing_events`: every webhook stored once by its event id.
- Payment states: trial, active, past due with a grace period, read-only, suspended, cancelled.
- Plan limits wired to module 8: seats, leads, proposals, sources, prospecting.
- The full self-service journey: sign up, create company, onboarding, choose plan, pay, first leads from the backfill within minutes.
- Legal pages: terms, privacy policy, data processing agreement, acceptable use, cookie notice, and the list of outside services that handle customer data.
- Data rights: export my data, delete my company (a full purge job), and a public form where a person can ask to be removed from the lead data.
- A final security pass: every module's terminal tests in one command, whole-repo scans, an active scan of staging, all keys rotated.
- Launch basics: support inbox, status page, welcome emails, in-app help, pricing page.
- A second-instance drill: deploy a separate branded copy using only configuration.
- Optional extras, each behind a feature: a WhatsApp digest through the official Business API, and an API with an MCP server so customers can read leads and approve drafts from their own tools.

## Build steps

1. Choose the payment route and open the account. Approval can take days, so start early.
2. Build `BillingProvider`, checkout and the customer portal.
3. Build the webhook handler: verify the signature, store the event id, ignore repeats, tolerate events arriving out of order.
4. Sync plans to permissions, and define upgrade and downgrade behaviour.
5. Polish the first-run experience, including sample leads while the backfill runs.
6. Write the legal pages and have a lawyer review them.
7. Build export, deletion and the removal form.
8. Add a `make security-suite` target that runs every module's terminal tests.
9. Run the full security pass, fix what it finds, run it again.
10. Do the second-instance drill.
11. Launch quietly with three to five friendly agencies and track their results.

## System design checks

- The payment provider is the source of truth for payment state. Your database changes only through verified webhooks.
- Webhooks can arrive twice or out of order without harm.
- The path from failed payment to suspension is defined, with dates the customer can see.
- Deleting a tenant removes or anonymises its rows, files, vectors and traces, and the backup policy says when old backups expire.
- The second instance needs no code change.
- Sign-up to first lead takes under 10 minutes.

## Security checks

- Webhooks without a valid signature, or older than a few minutes, are rejected.
- Checkout sessions are created on the server from a plan key. Prices from the browser are never trusted.
- Customers cannot change their own plan or status in the database.
- No card data touches your servers.
- Changing an account email needs a fresh sign-in, and customers can turn on a second factor.
- Whole-repo scans show no high or critical findings, and every key has been rotated before launch.
- The list of platform admins has been reviewed and trimmed.
- Consider paying a freelance security tester for one day before launch. A second pair of eyes finds what the author cannot.

## Other checks

- Legal review covers admin access to tenant data and the fact that your own company uses the same lead pool.
- Pricing has been tested in at least five conversations with real agencies.
- Sales tax and invoices are handled, by the merchant of record or by you.
- Support load: a short FAQ answers the ten questions the friendly agencies asked.
- Results: reply rate and wins from the quiet launch are written down. They are your sales material.

## Manual tests

1. In a private window, as a stranger: sign up, onboard, choose a plan, pay with a test card, and reach an inbox with leads within 10 minutes.
2. Pay with a test card that is declined. The message is clear and no access is granted.
3. Upgrade the plan. New features unlock within a minute.
4. Downgrade. Features lock at the end of the paid period.
5. Cancel in the customer portal. Access continues to the period end, then becomes read-only.
6. Simulate a failed renewal. A grace banner appears, and after the grace period the account is suspended.
7. Export your data. The file has leads, proposals and settings.
8. Delete the company. Sign-in fails, the admin panel shows it gone, and its files are gone.
9. Submit a removal request for a test person. Their lead disappears for every tenant and stays out after the next fetch.
10. Deploy the second branded instance with a different logo and domain. It works.
11. Read every legal page as a customer would.

## Terminal tests

```
# Forged payment webhook with no valid signature: expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/webhooks/billing" -H "Content-Type: application/json" \
  -d "{\"type\":\"subscription.updated\",\"data\":{\"tenant_id\":\"$TENANT_A\",\"status\":\"active\",\"plan\":\"agency_pro\"}}"

# Replay: resend one real test event twice from the provider's dashboard or CLI: expect 1
psql "$DB_URL" -c "select count(*) from billing_events where provider_event_id='$EVENT_ID';"

# Old event replayed with its original signature: expect 400
python -m api.cli replay-webhook --file saved_event.json --age-minutes 30

# A customer upgrades itself in the database: expect [] (no rows changed)
curl -s -X PATCH "$SUPA/rest/v1/tenants?id=eq.$TENANT_A" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" \
  -H "Content-Type: application/json" -H "Prefer: return=representation" \
  -d '{"plan":"agency_pro","status":"active"}'

# Checkout with a made-up price: expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/billing/checkout" \
  -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" -d '{"price_id":"price_fake","amount":1}'

# Suspended customer calls the API: expect 402 or 403
curl -s -o /dev/null -w "%{http_code}\n" "$API/leads" -H "Authorization: Bearer $JWT_SUSPENDED"

# After deleting a tenant: expect zero rows in every table and no files
python -m api.cli verify-purge --tenant $DELETED_TENANT

# Removal request holds: fetch again, expect the person still absent
python -m worker.cli run-source hackernews && python -m api.cli verify-suppressed --handle "$TEST_HANDLE"

# Export contains only the caller's data: expect 0
curl -s "$API/export" -H "Authorization: Bearer $JWT_A" | grep -c "$TENANT_B"

# Whole-repo scans: expect no high or critical findings
semgrep scan --config auto --severity ERROR .
gitleaks detect --source . --redact
pip-audit && (cd apps/web && npm audit --audit-level=high)
trivy fs --severity HIGH,CRITICAL .

# Active scan, staging only, never production: expect no high alerts
docker run --rm -t ghcr.io/zaproxy/zaproxy:stable zap-full-scan.py -t "$STAGING_WEB"

# Every module's terminal tests in one run: expect all green
make security-suite
```

## Tools

Command: `/security-review` on the whole repo. Skills: Trail of Bits `static-analysis`, `differential-review` and `supply-chain-risk-auditor`; your `module-done` across all modules. Plugins: `playwright` for the full sign-up journey. MCP or CLI: your payment provider's, in test mode only.

## Done when

- [ ] A stranger completes sign-up, payment and onboarding and sees leads within 10 minutes
- [ ] Payment state changes only through verified webhooks
- [ ] Export, deletion and removal requests work end to end
- [ ] All module terminal tests pass in one run and scans show no high findings
- [ ] Terms, privacy policy and data agreement are reviewed and published
- [ ] Phase 3 gate: a paying customer who never spoke to you
