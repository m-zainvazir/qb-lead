# 9 · Admin panel

## Goal

You can see and steer everything from one place: tenants, leads, sources, costs, catalogue and permissions. Every look across a company boundary is logged with a reason.

## What gets built

A separate `/admin` area for platform admins only, with multi-factor sign-in, served from its own host name in production.

| Screen | Shows | Lets you |
| --- | --- | --- |
| Overview | Today's funnel from fetched to won, spend against the cap, failing sources, queue length | Jump to the problem |
| Tenants | Plan, members, last active, usage against quota, matches, proposals, reply and win rates | Create, suspend, change plan, edit permissions and profile, view as that tenant |
| Lead explorer | Every lead, its raw item, classifier output, trace link, and each agency's match decision with the reason | Reclassify, mark as spam, push a lead to a tenant by hand, block an author or domain |
| Sources | Status, schedule, last run, yield, errors, cost per qualified lead, risk level | Switch on or off, change schedule, queries and caps, run now |
| Costs | Spend by provider, source, tenant and model, with a month-end projection | Set budgets and alert levels |
| Catalogue | Services, problems, technologies, markets with order and weights, signal types | Add and edit them |
| Permissions | Features, plans and per-tenant overrides from module 8 | Allow, lock, hide, grant a trial |
| Audit log | Who did what, to which tenant, when and why | Filter and export |

Also built:

- Admin API routes under `/admin`, guarded by `platform_admins`, using the system database path.
- View as: a read-only session tied to one tenant, with a visible banner, a 30-minute limit and a required reason.
- Two admin levels: super (everything) and support (read only, no exports).
- Summary tables refreshed on a schedule for the heavy totals.

## Build steps

1. Build the admin guard, enforce multi-factor sign-in, and set up the separate route group.
2. Build Tenants and the permissions editor.
3. Build the lead explorer with the stored "why" record.
4. Build Sources.
5. Build Costs, reading `usage_events`.
6. Build the catalogue, markets and signals editors.
7. Build the audit log viewer.
8. Build view as.
9. Build Overview last, since it summarises the rest.
10. Remove the temporary sources page and the `api.cli` permission commands from daily use.

## System design checks

- The admin panel reads the same tables as the product. There are no separate admin copies of data.
- Heavy totals come from summary tables, not from scanning live tables on each page load.
- Admin writes go through the same functions as customer writes, never straight to tables from screen code.
- View as never creates a customer login. The backend serves read-only data.
- The explorer's reason comes from the stored record, not a fresh calculation.
- The admin area can be switched off or moved to another host without touching the product.

## Security checks

- Every `/admin` route returns 403 to non-admins. A test lists the routes from the OpenAPI file and tries each one.
- Admin sessions need multi-factor sign-in, expire quickly, and ask again before destructive actions.
- The audit log records reads of tenant data as well as writes, and cannot be altered.
- The support level cannot write or export.
- The admin host has a stricter content security policy and can be limited to known IP addresses.
- Pushing a lead to a tenant by hand and overriding a source's risk level both need a reason.
- Secrets such as Slack addresses and webhook secrets are shown masked.
- Exports are protected against spreadsheet formula injection.

## Other checks

- Terms: customers are told that platform admins can access tenant data and that access is logged. This matters more because your own company is also a customer.
- Consider showing each customer its own access log. It builds trust cheaply.
- Speed: screens stay usable with 100 tenants and one million raw items.
- Reversibility: suspend before delete; every destructive action has an undo window or a confirmation.

## Manual tests

1. Sign in as a platform admin with no second factor set. You are forced to set one up.
2. Open Tenants, pick Agency B, press View as, give a reason. A banner shows, the data is read-only, and an edit attempt is blocked.
3. Open the audit log. The view-as session is there with your reason.
4. In the lead explorer pick a lead. You can see which agencies got it and why the others did not.
5. Change a source's schedule and cap, then press Run now. The run appears.
6. Change France's market weight, send a French lead, and see the score change.
7. Add a signal type and a service. They appear in customer settings and onboarding.
8. Suspend Agency B. B's users see a suspended notice and get no new matches. Lift the suspension.
9. Sign in at support level. There are no edit controls and no export button.
10. Compare the Costs total with the sum of the runs you just triggered. They agree.
11. Lock a feature for Agency B from the Permissions screen. It locks in B's interface.

## Terminal tests

```
# List every admin route from the OpenAPI file
curl -s "$API/openapi.json" | python3 -c "
import json,sys
spec=json.load(sys.stdin)
for p,ms in spec['paths'].items():
    if p.startswith('/admin'):
        for m in ms: print(m.upper(), p)" > admin_routes.txt

# Try each one as a normal customer: expect only 403 (any 200 is a failure)
while read m p; do printf "%s %s -> " "$m" "$p"
  curl -s -o /dev/null -w "%{http_code}\n" -X "$m" "$API$p" -H "Authorization: Bearer $JWT_A"; done < admin_routes.txt

# No token at all: expect 401
curl -s -o /dev/null -w "%{http_code}\n" "$API/admin/tenants"

# Admin without the second factor: expect 403
curl -s -o /dev/null -w "%{http_code}\n" "$API/admin/tenants" -H "Authorization: Bearer $JWT_ADMIN_NO_MFA"

# Support level tries to write and to export: expect 403 twice
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/admin/tenants/$TENANT_B/suspend" -H "Authorization: Bearer $JWT_SUPPORT"
curl -s -o /dev/null -w "%{http_code}\n" "$API/admin/audit/export" -H "Authorization: Bearer $JWT_SUPPORT"

# View as cannot write: expect 403
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH "$API/admin/view-as/$TENANT_B/leads/$LEAD_B/status" \
  -H "Authorization: Bearer $JWT_ADMIN" -H "Content-Type: application/json" -d '{"status":"won"}'

# View as without a reason: expect 422
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/admin/view-as/$TENANT_B" \
  -H "Authorization: Bearer $JWT_ADMIN" -H "Content-Type: application/json" -d '{}'

# Reading a tenant leaves a trail: expect 1 or more
curl -s "$API/admin/tenants/$TENANT_B" -H "Authorization: Bearer $JWT_ADMIN" >/dev/null
psql "$DB_URL" -c "select count(*) from audit_log where action='admin.tenant.read'
  and tenant_id='$TENANT_B' and at > now() - interval '1 minute';"

# Secrets are masked in admin responses: expect 0
curl -s "$API/admin/tenants/$TENANT_B" -H "Authorization: Bearer $JWT_ADMIN" | grep -c "hooks.slack.com/services/"

# Export with a formula in a lead title: expect clean
curl -s "$API/admin/leads/export" -H "Authorization: Bearer $JWT_ADMIN" | grep -nE '(^|,)[=+@-]' && echo UNSAFE || echo clean

# The customer host does not serve the admin area: expect 404
curl -s -o /dev/null -w "%{http_code}\n" "https://app.example.com/admin"
```

## Tools

Plugins: `feature-dev` (plan the screens first), `frontend-design`, `playwright`, `supabase`. Skills: your `design-check`. Command: `/security-review`.

## Done when

- [ ] Every admin route refuses non-admins in the automated route test
- [ ] View as is read-only, time-limited and logged with a reason
- [ ] You can answer "why did this agency get or miss this lead?" from the explorer
- [ ] Sources, markets, signals, catalogue and permissions are all editable without code
