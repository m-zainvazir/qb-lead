"""Platform admin module: the one logged path for reading across companies.

Guarded by `platform_admins` (its own table, not a tenant role) plus MFA (aal2).
One of only two places allowed to use system_db() (the other is the worker).
"""
