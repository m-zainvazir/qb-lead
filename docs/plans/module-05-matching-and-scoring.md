# 5 · Matching and scoring

## Goal

Each ready lead is scored against every profile, every agency that fits receives it, and the system can explain each decision afterwards. No model is called here, so matching stays fast and nearly free.

## What gets built

- `lead_matches`: tenant, lead, score from 0 to 100, score parts, rule results, the threshold in force, profile version, classifier version, status, time. One row per tenant and lead.
- A tenant read path to lead content that returns a lead only where a match row exists for the caller's tenant. Customers never query the pool.
- Score parts, each a small tested function: service fit (similarity between the lead and the profile's service fingerprints), intent, budget fit, market weight, buyer size preference, freshness, and signal weights.
- Hard rules that pass or fail: language, excluded keywords and industries, minimum budget when the budget is known, switched-off lead types, switched-off markets.
- Two thresholds per tenant: show in inbox, and send an alert.
- Distribution rule: every profile above its threshold gets the lead. Columns for `max_recipients` and `early_access_minutes` exist but are unused, ready for future plans.
- Backfill: a new or changed profile is scored against the last 14 days of leads.
- The "why" record, written at match time and never recalculated.
- `match_feedback`: thumbs up or down with a reason, for tuning later.

## Build steps

1. Build the table, policies and the tenant read path.
2. Build each score part as a pure function with unit tests.
3. Build the hard rules.
4. Build the matching task, triggered when a lead becomes ready. Use a vector search for the top candidate profiles first, so work does not grow as tenants times leads.
5. Build the backfill on profile change.
6. Write a golden set: 30 lead and profile pairs with the expected answer.
7. Add the feedback endpoint.
8. Write a plain-words explanation template, for example "Matches your voice agent service; budget above your minimum; posted 2 hours ago".

## System design checks

- Matching gives the same answer for the same inputs, with no model call per tenant.
- The "why" record stores the inputs at decision time, so later setting changes do not rewrite history.
- A profile change re-scores that profile only.
- Private leads match only their own tenant.
- Weights and thresholds are data. Changing one needs no deploy.
- 1,000 leads against 100 profiles completes in under a minute.

## Security checks

- A customer can read a lead only through its own match row. Direct pool access returns nothing.
- Customers cannot create match rows or point one at another lead.
- Customers can update only status and feedback on their own rows, never the score.
- A customer cannot learn which other agencies received a lead.
- Score parts never reveal another tenant's settings.

## Other checks

- Fair play: a test proves your own company's tenant gets no hidden boost. The same rules apply to `is_internal`.
- Quality: track the golden set pass rate and review the top reasons for dismissed leads each week.
- Wording: a non-technical person can read the explanation and agree with it.

## Manual tests

1. Set up Agency A for voice agents and Agency B for web development. Send a voice-agent lead. Only A receives it.
2. Send a lead that needs both services. Both receive it, each with its own score.
3. Raise A's minimum budget above the lead's budget and send again. A does not receive it.
4. Add "crypto" to A's exclusions and send a crypto lead. A does not receive it.
5. Turn France off in A's markets and send a lead from France. A does not receive it.
6. Create a brand new profile. Within a minute, recent matching leads appear.
7. Open "why this matched" on a lead. The explanation reads sensibly.
8. Lower a weight in the database, send a similar lead, and confirm the score moved with no deploy.

## Terminal tests

```
# Agency A reads Agency B's matches: expect []
curl -s "$SUPA/rest/v1/lead_matches?tenant_id=eq.$TENANT_B" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"

# Agency A opens a lead it was not matched to: expect 404
curl -s -o /dev/null -w "%{http_code}\n" "$API/leads/$LEAD_ONLY_B" -H "Authorization: Bearer $JWT_A"

# Agency A gives itself a match: expect a permission error
curl -s -X POST "$SUPA/rest/v1/lead_matches" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_A\",\"lead_id\":\"$LEAD_ONLY_B\",\"score\":99}"

# Agency A edits its own score: expect the score unchanged afterwards
curl -s -X PATCH "$SUPA/rest/v1/lead_matches?lead_id=eq.$LEAD_A" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" -d '{"score":100}'
psql "$DB_URL" -c "select score from lead_matches where lead_id='$LEAD_A' and tenant_id='$TENANT_A';"

# Walk through lead ids looking for leaks: expect 404 for every id not matched to A
for id in $(cat sample_lead_ids.txt); do
  curl -s -o /dev/null -w "%{http_code} $id\n" "$API/leads/$id" -H "Authorization: Bearer $JWT_A"; done

# The response for a matched lead shows no other tenant: expect no match
curl -s "$API/leads/$LEAD_BOTH" -H "Authorization: Bearer $JWT_A" | grep -c "$TENANT_B"

# Golden set and the no-favouritism test: expect all pass
pytest apps/worker/tests/test_matching_golden.py apps/worker/tests/test_internal_tenant_parity.py -q

# Speed: expect under 60 seconds
python -m worker.cli bench-matching --leads 1000 --tenants 100

# Same lead matched twice: expect one row per tenant
python -m worker.cli match-lead $LEAD_A && python -m worker.cli match-lead $LEAD_A
psql "$DB_URL" -c "select tenant_id, count(*) from lead_matches where lead_id='$LEAD_A' group by 1;"
```

## Tools

Skills: your `rls-test` and `design-check`. Plugins: `supabase` (inspect the read path and policies), `context7` (pgvector indexes), `code-review`.

## Done when

- [ ] Leads reach only the profiles they fit, and each match stores its "why"
- [ ] Customers can read a lead only through their own match
- [ ] The golden set and the fair-play test pass in CI
- [ ] Changing a weight or threshold needs no deploy
