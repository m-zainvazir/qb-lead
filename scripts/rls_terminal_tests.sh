#!/usr/bin/env bash
# Module 1 terminal tests 1-11 (docs/plans/module-01-tenants-and-isolation.md), local stack or STAGING (never production).
#
#   make seed-test && bash scripts/rls_terminal_tests.sh
#
# Commands are the plan's, with two adaptations:
#   * `psql` is scripts/psql.py (see scripts/terminal_env.sh); there is no Postgres install.
#   * test 9 needs a production web build in apps/web/.next (run `npm run build` first).
set -uo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/terminal_env.sh


echo "# 1. No login: expect 401 or an empty list, never rows"
curl -s "$SUPA/rest/v1/memberships?select=*" -H "apikey: $ANON"; echo

echo "# 2. Agency A asks for Agency B's rows: expect []"
curl -s "$SUPA/rest/v1/memberships?tenant_id=eq.$TENANT_B&select=*" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"; echo

echo "# 3. Agency A writes into Agency B: expect a row-level security error"
curl -s -X POST "$SUPA/rest/v1/invitations" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_B\",\"email\":\"x@example.com\",\"role\":\"admin\"}"; echo

echo "# 4. A member promotes themself: expect [] (no rows changed)"
curl -s -X PATCH "$SUPA/rest/v1/memberships?user_id=eq.$USER_MEMBER_A" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_MEMBER_A" \
  -H "Content-Type: application/json" -H "Prefer: return=representation" \
  -d '{"role":"owner"}'; echo

echo "# 5. Tampered token: expect 401"
curl -s -o /dev/null -w "%{http_code}\n" "$API/me" -H "Authorization: Bearer ${JWT_A}x"

echo "# 6. Wrong company in the request: Agency A's token with Agency B's id: expect 403"
curl -s -o /dev/null -w "%{http_code}\n" "$API/team" \
  -H "Authorization: Bearer $JWT_A" -H "X-Tenant-Id: $TENANT_B"

echo "# 7. Normal user on an admin route: expect 403"
curl -s -o /dev/null -w "%{http_code}\n" "$API/admin/tenants" -H "Authorization: Bearer $JWT_A"

echo "# 8. Tables without row-level security: expect zero rows"
psql "$DB_URL" -c "select relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relkind='r' and not c.relrowsecurity;"

echo "# 9. Service key in the browser bundle: expect clean"
if [ -d apps/web/.next/static ]; then
  grep -R "$SUPABASE_SERVICE_ROLE_KEY" apps/web/.next/static && echo LEAK || echo clean
else
  echo "SKIPPED: no apps/web/.next/static (run: cd apps/web && npm run build)"
fi

echo "# 10. Audit log cannot be altered by the app role: expect permission denied"
psql "$APP_DB_URL" -c "delete from audit_log;"

echo "# 11. The whole isolation suite: expect all pass"
uv run pytest tests/isolation -q
