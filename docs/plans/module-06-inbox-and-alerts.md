# 6 · Lead inbox and alerts

## Goal

A customer opens the app, sees ranked leads with the reason for each, works them through stages, and hears about hot ones within a minute. This is the first module a customer can actually see.

## What gets built

- Inbox screen: ranked list with filters for hot or warm, source, service, market, status and date, plus search.
- Lead detail screen: summary, original text and link, why it matched, budget, buyer, timeline and notes.
- Pipeline board: new, shortlisted, proposal drafted, sent, replied, won, lost.
- Team features: assign a lead, see who changed what.
- Tables: `lead_notes`, `lead_events` (every status change with who and when), `assignments`, `notification_settings` (channels, thresholds, quiet hours, digest time, time zone), `notifications` (queue and delivery status), `integrations` (Slack address, stored encrypted).
- Alerts: an instant Slack message and email for hot leads above the alert threshold, and a daily digest of warm leads at the customer's local time. One lead produces one alert per channel.
- A channel interface, so WhatsApp or Telegram can be added later as one class each.
- Email through a transactional provider, with SPF, DKIM and DMARC set on your sending domain.
- Clear empty states, including a "why am I seeing nothing?" helper that links to the profile and sources.

## Build steps

1. Build the API routes: inbox (paged and filterable), lead detail, status change, notes, assignment.
2. Build the inbox and detail screens.
3. Build the pipeline board.
4. Build the notification queue and channel interface, then the Slack and email senders.
5. Build the digest job with time zones and quiet hours.
6. Build the alert settings screen with a Send test alert button.
7. Refresh the inbox by polling every 30 seconds. Live updates can come later.

## System design checks

- Every status change goes through one route that writes `lead_events`.
- The inbox query uses an index on tenant, status, score and date, and stays fast at 50,000 matches.
- Alerts are queued and retried. A Slack outage neither loses alerts nor blocks the pipeline.
- An alert carries a summary and a link, not the whole lead, which limits where data spreads.
- Alerts are capped per hour per tenant and grouped when many arrive together.

## Security checks

- Every list and detail route is limited to the caller's tenant and to its match rows.
- Lead text is shown as plain text. Only web links are clickable, and they open safely.
- Actions that rely on cookies are protected against cross-site requests.
- A Slack address must be a real Slack webhook address. Anything else is refused, and the address is stored encrypted.
- Emails contain no user-controlled headers and include a preferences link.
- A member sees only what the role allows.
- The web app sends security headers: content security policy, strict transport security, no content sniffing, no framing.

## Other checks

- Accessibility: keyboard navigation, visible focus, readable contrast, usable on a phone.
- Time: digests arrive at local time, including across daylight-saving changes.
- Speed: the inbox loads in under one second at 10,000 matches.
- Email health: SPF, DKIM and DMARC records pass.

## Manual tests

1. Send a hot lead. A Slack message and an email arrive within a minute, and the link opens the lead.
2. Open the inbox on a phone. It is readable and the filters work.
3. Filter by hot, voice agents and the last 7 days. The list matches what you expect.
4. Move a lead to shortlisted, add a note and assign it to a teammate. The teammate sees it and the timeline shows each event.
5. Set quiet hours to cover now and send a hot lead. No alert arrives until quiet hours end.
6. Turn off the network and change a status. A clear error appears and nothing is silently lost.
7. Open a brand new account with no leads. The empty state explains what to do next.
8. Send a lead whose title contains `<script>alert(1)</script>`. It shows as text in the inbox, in Slack and in the email.
9. Send 30 hot leads in a minute. Alerts are grouped, not 30 separate messages.

## Terminal tests

```
# Read and change another agency's lead: expect 404 twice
curl -s -o /dev/null -w "%{http_code}\n" "$API/leads/$LEAD_ONLY_B" -H "Authorization: Bearer $JWT_A"
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH "$API/leads/$LEAD_ONLY_B/status" \
  -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" -d '{"status":"won"}'

# Add a note to another agency's lead: expect 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/leads/$LEAD_ONLY_B/notes" \
  -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" -d '{"body":"hi"}'

# Assign a lead to a user from another agency: expect 400 or 404
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "$API/leads/$LEAD_A/assignee" \
  -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" -d "{\"user_id\":\"$USER_B\"}"

# Slack address pointed at an internal address: expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "$API/settings/alerts/slack" \
  -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d '{"webhook_url":"http://169.254.169.254/"}'

# Request from another website using the session cookie: expect 403
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH "$API/leads/$LEAD_A/status" \
  -H "Origin: https://evil.example" -H "Cookie: $SESSION_COOKIE_A" \
  -H "Content-Type: application/json" -d '{"status":"lost"}'

# Security headers: expect all four present
curl -sI "$WEB/" | grep -iE "content-security-policy|strict-transport-security|x-content-type-options|x-frame-options"

# Passive scan of the web app: expect no high alerts
docker run --rm -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t "$WEB"

# Fuzz every API route from the OpenAPI file: expect no server errors
schemathesis run "$API/openapi.json" --header "Authorization: Bearer $JWT_A" --checks all

# Email records: expect SPF, DKIM and DMARC entries
dig +short TXT yourdomain.com
dig +short TXT _dmarc.yourdomain.com

# Stored Slack address is encrypted: expect no readable hooks.slack.com text
psql "$DB_URL" -c "select count(*) from integrations where config::text like '%hooks.slack.com%';"
```

## Tools

Plugins: `frontend-design`, `playwright` (turn the manual tests into scripts), `context7`, `code-review`. Command: `/security-review`. Command line: OWASP ZAP, schemathesis.

## Done when

- [ ] A hot lead produces a Slack and an email alert within a minute
- [ ] Inbox, detail and pipeline work on desktop and phone
- [ ] Every status change appears in the timeline
- [ ] ZAP shows no high alerts and schemathesis finds no server errors
