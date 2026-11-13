#!/usr/bin/env bash
# Module 2 terminal tests (docs/plans/module-02-catalogue-and-onboarding.md), LOCAL ONLY.
#
#   make seed-test && bash scripts/m2_terminal_tests.sh
#
# Commands are the plan's. Fixtures (sample.pdf, big.pdf, fake.pdf) are created in a
# temporary folder; a real sample.pdf is first uploaded to Agency B and Agency A so the
# cross-company download tests have a file to aim at.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

[ -f .env.test.local ] || { echo "Run 'make seed-test' first."; exit 2; }
# shellcheck disable=SC1091
source .env.test.local
case "$SUPA" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) echo "Refusing: SUPA is not a local stack ($SUPA)"; exit 2 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
uv run --project "$ROOT" python "$ROOT/scripts/make_sample_pdf.py" sample.pdf

# Setup (not a test): real files in both companies' folders.
for pair in "$JWT_B:$TENANT_B" "$JWT_A:$TENANT_A"; do
  jwt="${pair%%:*}"; tenant="${pair##*:}"
  curl -s -o /dev/null -X POST "$SUPA/storage/v1/object/portfolio/$tenant/sample.pdf" \
    -H "apikey: $ANON" -H "Authorization: Bearer $jwt" -H "Content-Type: application/pdf" \
    -H "x-upsert: true" --data-binary @sample.pdf
done

echo "# A customer edits the shared catalogue: expect a permission error"
curl -s -X POST "$SUPA/rest/v1/services" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d '{"name":"Injected service"}'; echo

echo "# Agency A reads Agency B's profile and portfolio: expect [] twice"
curl -s "$SUPA/rest/v1/tenant_profiles?tenant_id=eq.$TENANT_B" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"; echo
curl -s "$SUPA/rest/v1/portfolio_items?tenant_id=eq.$TENANT_B&select=id,title" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"; echo

echo "# Agency A downloads Agency B's file by path: expect 400 or 404"
curl -s -o /dev/null -w "%{http_code}\n" "$SUPA/storage/v1/object/portfolio/$TENANT_B/sample.pdf" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"

echo "# Public link to a private file: expect 400 or 404"
curl -s -o /dev/null -w "%{http_code}\n" "$SUPA/storage/v1/object/public/portfolio/$TENANT_A/sample.pdf"

echo "# Agency A uploads into Agency B's folder: expect a policy error"
curl -s -X POST "$SUPA/storage/v1/object/portfolio/$TENANT_B/evil.pdf" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" --data-binary @sample.pdf; echo
echo "#   (same, with a valid PDF content type, so the folder policy itself is tested)"
curl -s -X POST "$SUPA/storage/v1/object/portfolio/$TENANT_B/evil.pdf"   -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/pdf"   --data-binary @sample.pdf; echo

echo "# Oversized upload: expect 413"
head -c 30000000 /dev/urandom > big.pdf
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/portfolio" -H "Authorization: Bearer $JWT_A" -F "file=@big.pdf"

echo "# Wrong content behind a .pdf name: expect 415"
printf 'MZ\x90\x00' > fake.pdf
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/portfolio" -H "Authorization: Bearer $JWT_A" -F "file=@fake.pdf"

echo "# Very long answer in the questionnaire: expect 422"
python3 -c "print('{\"tone\":\"' + 'a'*200000 + '\"}')" 2>/dev/null > long.json || python -c "print('{\"tone\":\"' + 'a'*200000 + '\"}')" > long.json
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "$API/profile" -H "Authorization: Bearer $JWT_A" \
  -H "Content-Type: application/json" --data-binary @long.json
