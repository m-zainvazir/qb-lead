# 8 · Permissions and automation modes

## Goal

You decide what each customer may use. Each customer decides what to switch on within that. Each automated step runs off, as a suggestion for approval, or automatically. One function answers every "is this allowed?" question.

## What gets built

- Tables: `features` (key, name, description, default visibility: hidden or locked), `plans` and `plan_features` (what each plan allows, with limits), `tenant_entitlements` (your per-customer overrides, with optional expiry), `tenant_feature_settings` (the customer's own switch and mode), `usage_counters` (use per period).
- `can(tenant, feature)`: returns allowed or not, visibility, limit and what remains. It replaces the stub from module 1.
- `mode(tenant, step)`: returns off, suggest or automatic for research, drafting, sending and follow-up.
- A written order of precedence, highest first: platform-wide kill switch, channel ceiling, your override for the tenant, the plan, the default.
- Channel ceilings: marketplace sending can never be higher than suggest.
- Enforcement in three places: the API refuses, the worker skips and logs, the interface hides or greys out.
- Starting feature list: each source, automatic research, proposal drafting, email sending, automatic sending, follow-ups, Slack alerts, WhatsApp alerts, prospecting, team seats, custom markets, custom signals, export, API access.
- Quotas for leads per month, proposals per month and seats, counted safely under parallel requests.
- Customer screen named Automation: one row per allowed feature, with a switch and a mode. Locked features appear greyed out or not at all, per feature.
- `/me/capabilities`: the route the interface reads to decide what to draw.
- Every change to an entitlement is written to the audit log.

## Build steps

1. Build the tables and seed the feature list with one default plan.
2. Build `can()` and `mode()` with unit tests for every level of precedence.
3. Swap the stub. Add an API guard, `requires("feature")`, to each gated route.
4. Add the check before each automated step in the worker.
5. Build `/me/capabilities` and make the interface read it.
6. Build the Automation screen.
7. Build quota counters with an atomic increment.
8. Add the kill switch per feature.
9. Cache answers for a short, stated time and clear the cache on change.

## System design checks

- One function decides. There are no scattered checks on the plan name.
- Hiding something in the interface is cosmetic. The server is what enforces.
- A new feature is one row and one `requires()`.
- Switching sending to automatic needs a logged opt-in by the tenant owner and has a daily cap.
- Losing a feature is defined: running automations stop at the next step and data is kept.
- You can grant a time-limited trial of any feature.

## Security checks

- Customers can read their own entitlements and never write them.
- A locked feature is refused when the API is called directly.
- Only an owner or admin of the tenant can change modes.
- After you revoke a feature, it stops working within the stated cache time.
- Parallel requests cannot push usage past a quota.
- The capabilities route shows nothing about other tenants or about features that are hidden.

## Other checks

- Wording for locked features is honest and offers a way to ask for access.
- Plans will map to prices in module 12, so plan keys are stable names.
- The decision on hidden versus greyed out is recorded per feature, since you have not chosen yet.

## Manual tests

Until the admin panel exists, change entitlements with the `api.cli` helper.

1. Disallow proposal drafting for Agency B. B's Draft button disappears or greys out, according to that feature's visibility.
2. Switch that feature's visibility between hidden and locked. The interface follows.
3. Allow it again. The button returns within a minute.
4. As Agency A's owner, set research to automatic. New hot leads get a brief with no click. Set it to off. They do not.
5. Set drafting to suggest. Drafts wait for approval.
6. Try to set marketplace sending to automatic. The option is not offered.
7. As a plain member, try to change a mode. It is refused.
8. Set a quota of 3 proposals a month. The fourth shows a clear limit message.
9. Grant a one-day trial and move its expiry into the past. The feature locks again.
10. Turn on the kill switch for automatic sending. It stops for every tenant.

## Terminal tests

```
# Locked feature called directly: expect 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/leads/$LEAD_B/proposals" -H "Authorization: Bearer $JWT_B"

# A customer grants itself a feature: expect a permission error
curl -s -X POST "$SUPA/rest/v1/tenant_entitlements" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_B" -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_B\",\"feature\":\"proposals.auto_send\",\"allowed\":true}"

# A customer edits an existing entitlement: expect [] (no rows changed)
curl -s -X PATCH "$SUPA/rest/v1/tenant_entitlements?tenant_id=eq.$TENANT_B" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_B" \
  -H "Content-Type: application/json" -H "Prefer: return=representation" -d '{"allowed":true}'

# A member, not an owner, switches a step to automatic: expect 403
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "$API/settings/automation/sending" \
  -H "Authorization: Bearer $JWT_MEMBER_A" -H "Content-Type: application/json" -d '{"mode":"auto"}'

# A mode above the channel ceiling: expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "$API/settings/automation/sending" \
  -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d '{"mode":"auto","channel":"marketplace"}'

# Quota race: 20 requests at once with 3 left: expect exactly 3 successes
seq 1 20 | xargs -P 20 -I{} curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "$API/leads/$LEAD_A/proposals" -H "Authorization: Bearer $JWT_A" | sort | uniq -c

# Revoke, wait past the cache time, call: expect 403
python -m api.cli revoke --tenant $TENANT_B --feature research.auto
sleep 65
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/leads/$LEAD_B/research" -H "Authorization: Bearer $JWT_B"

# The worker respects the switch: queue an automatic step for a tenant with it off: expect skipped
python -m worker.cli run-step research --lead $LEAD_B --tenant $TENANT_B

# Capabilities show nothing hidden: expect 0
curl -s "$API/me/capabilities" -H "Authorization: Bearer $JWT_B" | grep -c "prospecting"

# Precedence tests: expect all pass
pytest apps/api/tests/test_entitlements.py -q
```

## Tools

Skills: your `design-check` and `rls-test`. Plugins: `code-review`, `playwright`. Command: `/security-review`.

## Done when

- [ ] Every feature and automated step is gated through `can()` and `mode()`
- [ ] A locked feature is refused by the API, the worker and the interface
- [ ] Hidden versus greyed out is a setting per feature
- [ ] Quotas hold under parallel requests
