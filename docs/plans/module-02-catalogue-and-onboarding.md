# 2 Â· Service catalogue and onboarding profile

## Goal

A new customer answers a short questionnaire, and the system turns the answers into a profile that drives search terms, matching, scoring and proposal style. Two different customers end up with visibly different behaviour from the same code.

## What gets built

- Shared catalogue tables, editable only by platform admins: `services`, `problems` (business problems in plain words, with example phrases), `technologies` (with synonyms), and the links between them.
- Shared settings tables: `markets` (country, default weight, active) seeded with USA, UK, Canada, Australia, France and Portugal in that order; `signal_types` (key, hot or warm, default weight).
- Tenant tables: `tenant_profiles` (type, team size, minimum budget, preferred client sizes, tone, priorities, time zone, version), `tenant_services`, `tenant_markets`, `tenant_signals`, `tenant_exclusions`, `portfolio_items`.
- `onboarding_questions`: the questionnaire stored as data (key, type, options, order, branching rule), so new questions need no code.
- A profile compiler job. On every save it produces the profile's search terms per source and a meaning-based fingerprint per service (embeddings in pgvector), stamped with the profile version.
- Portfolio upload to a private Supabase Storage bucket, with text extraction and an embedding per item.
- Screens: onboarding wizard, profile editor, portfolio page, and a preview that says "here is what we will look for".
- Seed data: AI automation, voice agents and web development, each with about ten problems and its technologies.

## Build steps

1. Write the catalogue migrations and seed data.
2. Write the tenant profile tables from the module 1 template.
3. Store the questionnaire as data and render the wizard from it.
4. Build the profile compiler as a background job that is safe to run twice.
5. Put the embedding call behind an interface. Store the model name and vector size beside every vector.
6. Build portfolio upload, extraction and embedding.
7. Build the preview screen, using a small fixed set of sample posts.
8. Review the generated search terms by hand for the first five profiles.

## System design checks

- The catalogue is shared and tenants only link to it. A tenant's custom service stays private to that tenant.
- Every profile change creates a new version, and later matches record which version they used.
- Answers map to named fields. The pipeline never re-interprets free text at run time.
- Switching the embedding model is possible: there is a command to re-embed everything.
- The vector index type and size are fixed per model and written in the decision record.
- Adding a service, a market, a signal or a question is a data change only.

## Security checks

- The storage bucket is private, files sit under a folder named by tenant id, and storage policies check that folder.
- Download links are signed and short-lived.
- Uploads accept a short list of file types, have a size cap, and are checked by content, not by file name.
- Free-text answers have length limits and are treated as untrusted when they later enter a prompt.
- Only platform admins can write to catalogue, markets and signal tables.
- Text extraction runs in the worker with time and memory limits.

## Other checks

- The wizard takes under five minutes and resumes where the person left off.
- The cost of one profile save (embeddings) is recorded.
- The preview makes sense to someone who is not technical.

## Manual tests

1. Complete onboarding as a freelancer who offers voice agents. The preview mentions missed calls and phone answering.
2. Complete onboarding as an agency that offers web development with a 2,000 dollar minimum. The preview is clearly different.
3. Remove a service in the profile editor. The status shows updating, then the preview changes.
4. Upload a portfolio PDF. It appears with an extracted summary.
5. Rename a program file to `.pdf` and upload it. It is rejected.
6. Close the browser halfway through the wizard and reopen it. It resumes at the same step.
7. As platform admin, add a service called Chatbots. It appears as an option in onboarding without a deploy.

## Terminal tests

```
# A customer edits the shared catalogue: expect a permission error
curl -s -X POST "$SUPA/rest/v1/services" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" -H "Content-Type: application/json" \
  -d '{"name":"Injected service"}'

# Agency A reads Agency B's profile and portfolio: expect [] twice
curl -s "$SUPA/rest/v1/tenant_profiles?tenant_id=eq.$TENANT_B" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"
curl -s "$SUPA/rest/v1/portfolio_items?tenant_id=eq.$TENANT_B" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"

# Agency A downloads Agency B's file by path: expect 400 or 404
curl -s -o /dev/null -w "%{http_code}\n" "$SUPA/storage/v1/object/portfolio/$TENANT_B/sample.pdf" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"

# Public link to a private file: expect 400 or 404
curl -s -o /dev/null -w "%{http_code}\n" "$SUPA/storage/v1/object/public/portfolio/$TENANT_A/sample.pdf"

# Agency A uploads into Agency B's folder: expect a policy error
curl -s -X POST "$SUPA/storage/v1/object/portfolio/$TENANT_B/evil.pdf" \
  -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A" --data-binary @sample.pdf

# Oversized upload: expect 413
head -c 30000000 /dev/urandom > big.pdf
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/portfolio" -H "Authorization: Bearer $JWT_A" -F "file=@big.pdf"

# Wrong content behind a .pdf name: expect 415
printf 'MZ\x90\x00' > fake.pdf
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/portfolio" -H "Authorization: Bearer $JWT_A" -F "file=@fake.pdf"

# Very long answer in the questionnaire: expect 422
python3 -c "print('{\"tone\":\"' + 'a'*200000 + '\"}')" | \
  curl -s -o /dev/null -w "%{http_code}\n" -X PUT "$API/profile" -H "Authorization: Bearer $JWT_A" \
  -H "Content-Type: application/json" --data-binary @-
```

## Tools

Plugins: `supabase`, `context7` (pgvector and Supabase Storage), `frontend-design`, `playwright`. Skills: your `design-check` and `rls-test`.

## Done when

- [x] Two different questionnaires produce visibly different search terms and fingerprints (2026-11-14: Agency A voice-agent freelancer vs Agency B web-development agency; different queries, exclusions, fingerprints and preview)
- [x] A new service, market, signal or question can be added as data, with no code change (admin API and screen; each shows up in onboarding at once and disappears when switched off)
- [x] Profile edits recompile in the background and are versioned (one version per save; worker job plus a 30 s sweep)
- [x] Storage and catalogue terminal tests pass (`bash scripts/m2_terminal_tests.sh`; the plan's A-into-B upload has no content type and is refused by the bucket's type list, so a second call with a PDF type proves the folder policy)
