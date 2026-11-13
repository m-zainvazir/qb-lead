# Privacy notes

What personal data the platform stores, why, for how long, and how it is deleted. Updated per module.

## Module 1: accounts, companies, team

| Data | Where | Why | Kept |
| --- | --- | --- | --- |
| Email, password hash, sign-in timestamps, sessions, MFA factors | Supabase Auth (`auth.users`, `auth.sessions`, `auth.mfa_factors`) | Sign-in | Until the account is deleted |
| Company name, type, branding | `public.tenants` | Customer account | Until the company is hard-deleted |
| Membership: user, company, role | `public.memberships` | Who belongs to which company | Until removed, or the user is deleted (cascade) |
| Invited email, role, token hash, timestamps | `public.invitations` | Team invitations | Until the company is deleted. **To do:** purge accepted, revoked and expired invitations after 30 days (worker job, module 10) |
| Platform admin flag | `public.platform_admins` | Staff access | Until removed by SQL |
| Audit log: actor id, company id, action, target, request id, IP address | `public.audit_log` | Security and accountability | Append-only. **To decide:** retention period (proposal: 2 years), then archive and delete through a deliberate job |

Passwords are never stored by us; Supabase stores a hash. Invitation tokens are stored only as SHA-256 hashes.

## Deleting an account (on request)

1. Check that the user is not the last owner of any active company. If they are, the company is transferred or suspended first; the database refuses to remove the last owner.
2. Delete the user in Supabase Auth (dashboard or admin API). Memberships cascade, and invitations the user sent cascade.
3. Audit entries keep the user's id but no email or name, so the log stays intact without the person's details. If a full erasure is required, the retention job handles it under a written decision.

## Deleting a company

1. Set `status = 'suspended'` or `'deleted'`. Members immediately lose access (RLS checks `status = 'active'`).
2. Hard deletion is a separate, deliberate job (module 9 or 10): it removes the company's rows table by table, then the company. It is never run from a screen in one click.

## Customer terms (to write before launch, module 12)

- Platform admins can access company data. Every such access is written to the audit log with the admin's identity and the time, and requires MFA.
- Sub-processors: Supabase (database, auth), the email provider, and later the AI and scraping providers.
