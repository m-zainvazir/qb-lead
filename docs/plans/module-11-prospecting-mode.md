# 11 · Prospecting mode

## Goal

A customer describes who they sell to. The system finds matching businesses, reads their websites for visible evidence of need, scores them, and drafts outreach that opens with that evidence. This is the method from the Ottermind example, built to run for many customers with limits, costs and country rules.

## What gets built

- Campaign setup built on four questions: what do I sell, who do I sell it to, where are they, and what on their site proves they need it.
- A signal library per service, for example "phone-only booking" and "no after-hours option" for voice agents. Customers pick from it or add their own.
- Tables: `campaigns` (service, target, location, signals, scoring rubric, schedule, daily limit, end rule), `prospects` (company, domain, page checked, evidence with quote and link, score and reason, contact email and the page it came from, contact route, status), `suppression_list` (per tenant and platform-wide), `country_rules` (whether unrequested email may be sent, what it must contain, date reviewed).
- A staged pipeline, each stage picking up rows by status:
    1. Discover businesses through search.
    2. Remove duplicates by domain.
    3. Read a few pages of each site through Firecrawl.
    4. Check each signal with the small model. A signal counts only with a quote and a link.
    5. Score. The rubric rewards the absence of what the customer sells, and checks the business is established enough to pay.
    6. Find a published contact address, recording the page it was on. Never guess one.
    7. Draft through the module 7 agent with an outreach template that opens with the evidence.
    8. Approval, then send or export.
- A validation step: sample five businesses first and show the hit rate before the campaign runs at volume.
- Limits: businesses per run, runs per day, sends per day per mailbox.
- Every email carries the sender's identity and a working opt-out link.
- The whole module sits behind the `prospecting` feature from module 8.
- `evals/evidence.jsonl`: 40 real sites labelled by hand for each signal.

## Build steps

1. Build the campaign tables, the four-question wizard and the signal library.
2. Build the discovery connector with the `connector-new` skill, and the domain deduper.
3. Build the site reader and the evidence checker with the strict "quote or nothing" rule.
4. Build the scoring rubric and the validation sample.
5. Build the contact finder for published addresses only.
6. Add the outreach template and an approval queue with a preview per item.
7. Build sending with limits, the opt-out link and the suppression list.
8. Build the `country_rules` table and its admin editor. Start conservative: USA can send, every other market is export-only until reviewed.
9. Build the evidence eval set and its command.

## System design checks

- It reuses the pipeline, proposal agent, cost recording and permissions. It is not a second system.
- A failed stage leaves rows waiting, and the next run picks them up.
- Batches are small by design, about eight businesses per run.
- Site facts may be cached for everyone by domain. Scores, evidence judgements and drafts belong to one tenant.
- Evidence is stored with link, quote and time, so a human can verify it with one click.
- Every campaign has an end rule, so nothing runs and costs money forever.

## Security checks

- Every site fetch goes through the internal-address guard and a per-domain rate limit.
- Business websites are untrusted text. The poisoned-website test from module 7 is repeated here.
- No guessed addresses and no personal contact details. Role addresses such as info@ are preferred.
- Customers send from their own domain, with daily caps, so one customer cannot damage everyone's sender reputation.
- Opt-out links use long random values, and an opt-out applies across all of that tenant's campaigns.
- The country gate is enforced on the server, not only in the interface.
- Prospects are tenant data with row-level security.

## Other checks

- Law: rules on unrequested business email differ by country. Of your markets the USA is the most permissive; Canada, the UK, Australia, France and Portugal are stricter. Get legal advice before enabling sending in each one.
- Quality: evidence precision of at least 0.80 on the labelled sites, and the hit rate shown to the customer.
- Cost: cost per qualified prospect, capped per campaign.
- Email health: the customer's domain passes SPF, DKIM and DMARC before sending is enabled.
- Abuse: the acceptable-use terms forbid harassment and repeated contact after an opt-out.

## Manual tests

1. Create a campaign: voice agents, dental clinics, Austin in Texas, signals "phone-only booking" and "no after-hours option". The validation step shows five businesses with evidence and a hit rate.
2. Start the campaign. About eight prospects appear with evidence quotes.
3. Click a quote's link. The quote really is on that page.
4. Find a business that has online booking. It is scored low or rejected, with a reason.
5. Open a drafted email. The first line refers to that business's own evidence, and the email has your identity and an opt-out line.
6. Find a prospect with no published address. It shows form only and has no Send button.
7. Add a domain to the suppression list and run again. It is skipped.
8. Set the campaign to a country marked export-only. Sending is disabled and the export works.
9. Click the opt-out link in a test email. A second send to that address is blocked.
10. Run the same campaign twice. No prospect appears twice.
11. Let a campaign reach its end rule. It stops by itself.

## Terminal tests

```
# Feature locked for Agency B: expect 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/campaigns" \
  -H "Authorization: Bearer $JWT_B" -H "Content-Type: application/json" \
  -d '{"service":"voice-agents","target":"dentists","location":"Austin, TX"}'

# Another agency's prospects and campaign: expect [] and 404
curl -s "$SUPA/rest/v1/prospects?tenant_id=eq.$TENANT_B" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"
curl -s -o /dev/null -w "%{http_code}\n" "$API/campaigns/$CAMPAIGN_B" -H "Authorization: Bearer $JWT_A"

# Send to a suppressed address: expect 409
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/prospects/$SUPPRESSED_PROSPECT/send" -H "Authorization: Bearer $JWT_A"

# Send in an export-only country: expect 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/prospects/$PROSPECT_FR/send" -H "Authorization: Bearer $JWT_A"

# Send without approval: expect 409
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/prospects/$DRAFTED_PROSPECT/send" -H "Authorization: Bearer $JWT_A"

# Daily send cap: expect 429 after the limit
for i in $(seq 1 80); do curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/prospects/test-send" \
  -H "Authorization: Bearer $JWT_A"; done | sort | uniq -c

# Guessing opt-out links: expect 404 for each, with the same message every time
for t in aaaa bbbb $(openssl rand -hex 16); do curl -s -o /dev/null -w "%{http_code}\n" "$API/u/$t"; done

# Evidence is real: every stored quote appears in the stored page text: expect 0 missing
python -m worker.cli verify-evidence --campaign $CAMPAIGN_A

# No guessed addresses: expect 0
psql "$DB_URL" -c "select count(*) from prospects where contact_email is not null and email_source_url is null;"

# Poisoned business site: expect pass
python -m worker.cli prospect --url "$POISON_URL" --campaign $CAMPAIGN_A --print \
  | grep -iE "system prompt|wire a deposit|12345" && echo FAIL || echo pass

# A campaign target pointing at an internal address: expect refused
python -m worker.cli prospect --url "http://10.0.0.5/" --campaign $CAMPAIGN_A

# Evidence quality set: expect precision at or above 0.80
python -m evals.run_evidence --set evals/evidence.jsonl --min-precision 0.80
```

## Tools

Skills: your `connector-new` and `llm-eval`. Plugins: `feature-dev`, `playwright`. MCP: Firecrawl. Command line: promptfoo. Command: `/security-review`.

## Done when

- [ ] A campaign produces prospects whose evidence a human can verify by clicking
- [ ] Businesses that already solved the problem score low
- [ ] No address is ever guessed, and suppressed addresses are never contacted
- [ ] Sending obeys country rules, daily caps and opt-outs
