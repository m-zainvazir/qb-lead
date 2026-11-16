"""Which Supabase projects tests, seeding, SQL scripts and migration pushes may touch.

Allowed: a local stack (127.0.0.1 / localhost) or a project ref listed in
`.claude/staging-targets.txt`. Refused: APP_ENV=production, anything listed in
`.claude/protected-targets.txt`, and every other host. Project refs are not secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
LOCAL_HOSTS = {"127.0.0.1", "localhost", "host.docker.internal"}


class UnsafeTarget(RuntimeError):
    pass


def _list(name: str, root: Path | None = None) -> list[str]:
    f = (root or ROOT) / ".claude" / name
    if not f.exists():
        return []
    return [
        line.strip()
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def project_ref(url: str) -> str | None:
    """The Supabase project ref named by an API or database URL, if any."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    user = parts.username or ""
    if host.endswith(".supabase.co"):
        labels = host.split(".")
        # <ref>.supabase.co  or  db.<ref>.supabase.co
        return labels[1] if labels[0] == "db" and len(labels) > 3 else labels[0]
    if host.endswith(".pooler.supabase.com") and "." in user:
        return user.rsplit(".", 1)[1]  # pooler logins are <role>.<ref>
    return None


def check(*urls: str, app_env: str | None = None, root: Path | None = None) -> str:
    """Raise UnsafeTarget unless every URL is local or an allowed staging project.

    Returns "local" or the staging project ref.
    """
    env = (app_env or os.environ.get("APP_ENV") or "").lower()
    if env == "production":
        raise UnsafeTarget("APP_ENV is production")
    protected = [p.lower() for p in _list("protected-targets.txt", root)]
    staging = {s.lower() for s in _list("staging-targets.txt", root)}
    kinds: set[str] = set()
    for url in urls:
        low = url.lower()
        for p in protected:
            if p in low:
                raise UnsafeTarget(f"a protected target is named ({p})")
        host = (urlsplit(url).hostname or "").lower()
        if host in LOCAL_HOSTS:
            kinds.add("local")
            continue
        ref = project_ref(url)
        if ref is None or ref not in staging:
            raise UnsafeTarget(
                f"{host or url!r} is neither local nor a staging project in "
                ".claude/staging-targets.txt"
            )
        kinds.add(ref)
    if len(kinds) > 1:
        raise UnsafeTarget(f"the URLs point at different targets: {sorted(kinds)}")
    return kinds.pop() if kinds else "local"
