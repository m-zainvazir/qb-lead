"""`make push-staging`: apply new migrations to the STAGING Supabase project.

Reads DATABASE_URL_ADMIN from .env and refuses unless it points at a project listed in
.claude/staging-targets.txt (never production; see core.targets). The Supabase CLI is
called directly here, so the guard_commands hook keeps blocking ad-hoc `supabase db push`.

  uv run python scripts/push_staging.py            # list pending, then apply
  uv run python scripts/push_staging.py --dry-run  # list pending only
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from dotenv import dotenv_values  # noqa: E402

from core.targets import UnsafeTarget, check  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    env = dotenv_values(ROOT / ".env")
    url = env.get("DATABASE_URL_ADMIN") or ""
    if not url:
        print("DATABASE_URL_ADMIN is not set in .env", file=sys.stderr)
        return 2
    try:
        ref = check(url, app_env=env.get("APP_ENV"))
    except UnsafeTarget as exc:
        print(f"Refusing to push: {exc}", file=sys.stderr)
        return 2
    if ref == "local":
        print("DATABASE_URL_ADMIN is local; nothing to push to staging.", file=sys.stderr)
        return 2
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("npx not found", file=sys.stderr)
        return 2
    cmd = [npx, "supabase", "db", "push", f"--remote={url}", "--yes"]
    if args.dry_run:
        cmd.append("--dry-run")
    print(f"Pushing migrations to staging project {ref}{' (dry run)' if args.dry_run else ''}")
    # Fixed argv (no shell); the only variable part is the checked staging URL.
    return subprocess.call(cmd, cwd=ROOT)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
