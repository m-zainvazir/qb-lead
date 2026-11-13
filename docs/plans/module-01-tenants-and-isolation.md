# 1 · Tenants, logins and isolation

## Goal

People sign in, belong to a company, and can only ever read that company's data. Named platform admins can read across companies through one logged path. This module is the wall between customers, so it gets the strictest tests in the project.

## What gets built

- Tables: `tenants` (name, type freelancer or agency, status, `is_internal`, branding settings), `memberships` (user, tenant, role: owner, admin or member), `platform_admins` (user, level: super or support), `invitations`, `audit_log`.
- Supabase Auth with email confirmation and password reset. Multi-factor sign-in for platform admins.
- Row-level security on every tenant table, using one helper function `is_member(tenant_id)` that checks `memberships` for the signed-in user.
- Two database paths in the backend, clearly named: `user_db(token)`, where row-level security applies, and `system_db()`, which uses the service-role key.
- `system_db()` may be imported only by the worker and the admin module. A lint rule enforces that.
- Admin routes under `/admin`, guarded by `platform_admins`. Every cross-company read writes an audit entry.
- Your own company is an ordinary tenant with `is_internal = true`. A member of your agency is not a platform admin unless added to `platform_admins`.
- A stub `can(tenant, feature)` that returns true. Module 8 replaces the inside, and no caller changes.
- Screens: sign up, sign in, reset password, create company, invite teammate, team list, switch company.

## Build steps

1. Write the migrations: tables, helper function, policies, indexes on `tenant_id`.
2. Create a migration template for all future tenant tables: `tenant_id`, index, row-level security on, four policies.
3. Build sign-up, sign-in and reset in Next.js with HTTP-only cookies.
4. Build the FastAPI login dependency: verify the token, load the membership, attach tenant and role to the request.
5. Build `user_db` and `system_db` and the import rule.
6. Build invitations: single-use, random, tied to one email, expire after 7 days.
7. Build the audit log writer and make the table append-only.
8. Add the platform admin guard. Create the first admin by SQL, never through a screen.
9. Write the `rls-test` skill and an isolation test suite that finds every table with a `tenant_id` and tests it.

## System design checks

- A user can belong to several companies. The active company is sent with each request and checked against `memberships` on the server.
- Platform admin is its own table, not a role inside a tenant.
- Exactly one place in the code creates a service-role connection.
- Branding and domain are tenant data, which keeps branded installs possible later.
- Tenants are suspended or soft-deleted first; hard deletion is a separate, deliberate job.
- The isolation suite discovers new tables by itself, so a forgotten policy fails CI.

## Security checks

- Row-level security is enabled and forced on every tenant table. Nothing is readable without a login.
- On insert, `tenant_id` is checked by the policy, so a user cannot write into another company.
- Only an owner can change roles, and nobody can raise their own role.
- Tokens are checked for signature, expiry and audience.
- Email confirmation, leaked-password protection and sign-in rate limits are on in Supabase.
- Sign-in and reset messages do not reveal whether an email exists.
- The service-role key is absent from the web bundle.
- The audit log allows inserts only: no update, no delete, even for the app's own database role.

## Other checks

- Privacy: list which user data is stored and how an account is deleted.
- Sessions: signing out, and resetting a password, end other sessions.
- Customer terms will need to say that platform admins can access tenant data and that access is logged.

## Manual tests

1. Sign up as the owner of Agency A, confirm the email, create the company.
2. Invite a teammate. Accept in a private window. The teammate sees Agency A only.
3. Sign up Agency B with a different email. Its team list shows nobody from A.
4. As a plain member of A, open team settings. Access is refused.
5. Copy a page address from Agency A's session into Agency B's session. It shows not found.
6. Sign in as platform admin and open Agency B. An audit entry appears with your name and the time.
7. Reset a password. The old session stops working.
8. Use an invitation link twice. The second use fails.

## Terminal tests

```
# 1. No login: expect 401 or an empty list, never rows
curl -s "$SUPA/rest/v1/memberships?select=*" -H "apikey: $ANON"

# 2. Agency A asks for Agency B's rows: expect []
curl -s "$SUPA/rest/v1/memberships?tenant_id=eq.$TENANT_B&select=*" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"

# 3. Agency A writes into Agency B: expect a row-level security error
curl -s -X POST "$SUPA/rest/v1/invitations" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_B\",\"email\":\"x@example.com\",\"role\":\"admin\"}"

# 4. A member promotes themself: expect [] (no rows changed)
curl -s -X PATCH "$SUPA/rest/v1/memberships?user_id=eq.$USER_MEMBER_A" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_MEMBER_A" \
  -H "Content-Type: application/json" -H "Prefer: return=representation" \
  -d '{"role":"owner"}'

# 5. Tampered token: expect 401
curl -s -o /dev/null -w "%{http_code}\n" "$API/me" -H "Authorization: Bearer ${JWT_A}x"

# 6. Wrong company in the request: Agency A's token with Agency B's id: expect 403
curl -s -o /dev/null -w "%{http_code}\n" "$API/team" \
  -H "Authorization: Bearer $JWT_A" -H "X-Tenant-Id: $TENANT_B"

# 7. Normal user on an admin route: expect 403
curl -s -o /dev/null -w "%{http_code}\n" "$API/admin/tenants" -H "Authorization: Bearer $JWT_A"

# 8. Tables without row-level security: expect zero rows
psql "$DB_URL" -c "select relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relkind='r' and not c.relrowsecurity;"

# 9. Service key in the browser bundle: expect clean
grep -R "$SUPABASE_SERVICE_ROLE_KEY" apps/web/.next/static && echo LEAK || echo clean

# 10. Audit log cannot be altered by the app role: expect permission denied
psql "$APP_DB_URL" -c "delete from audit_log;"

# 11. The whole isolation suite: expect all pass
pytest tests/isolation -q
```

## Tools

Plugins: `supabase`, `security-guidance`, `code-review`, `playwright`, `context7`. Skills: your `rls-test`, Trail of Bits `differential-review` on the migrations. Command: `/security-review` before merging.

## Done when

- [x] Two test agencies exist and every terminal test gives the expected result (2026-11-13, `bash scripts/rls_terminal_tests.sh` after a fresh `make db-reset`)
- [ ] The isolation suite covers every table with a `tenant_id` and runs in CI. Coverage: done (tables discovered automatically, a missing factory fails). CI: the `database` job exists in `.github/workflows/ci.yml` but has not run yet, because no GitHub remote exists.
- [x] Platform admin reads are written to the audit log (`admin.tenants_listed`, `admin.tenant_viewed`)
- [x] Only one module can open a service-role connection (`packages/core/core/db.py`; ruff TID251 plus `test_import_rules.py`)
- [ ] Sign-up, invite, reset and company switch work in the browser. Checked over HTTP (confirm link, cookies, team, invite and accept, cross-company not found); manual tests 1-8 in a real browser are still open.
