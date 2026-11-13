"""Fail when a migration creates a table without turning on row-level security.

    python scripts/check_migrations.py                 # every file in supabase/migrations
    python scripts/check_migrations.py path/to/x.sql   # just these files

Every `create table` must be followed, in the same file, by
`alter table <name> enable row level security` and `... force row level security`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"

_NAME = r'((?:"?[\w]+"?\.)?"?[\w]+"?)'
CREATE = re.compile(
    rf"\bcreate\s+(?:unlogged\s+)?table\s+(?:if\s+not\s+exists\s+)?{_NAME}", re.IGNORECASE
)
ENABLE = re.compile(
    rf"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?{_NAME}\s+enable\s+row\s+level\s+security",
    re.IGNORECASE,
)
FORCE = re.compile(
    rf"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?{_NAME}\s+force\s+row\s+level\s+security",
    re.IGNORECASE,
)
COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _norm(name: str) -> str:
    name = name.replace('"', "").lower()
    return name if "." in name else f"public.{name}"


def check(path: Path) -> list[str]:
    sql = COMMENT.sub("", path.read_text(encoding="utf-8"))
    created = {_norm(m.group(1)) for m in CREATE.finditer(sql)}
    enabled = {_norm(m.group(1)) for m in ENABLE.finditer(sql)}
    forced = {_norm(m.group(1)) for m in FORCE.finditer(sql)}
    errors = []
    for table in sorted(created):
        if table not in enabled:
            errors.append(f"{path.name}: {table} has no `enable row level security`")
        if table not in forced:
            errors.append(f"{path.name}: {table} has no `force row level security`")
    return errors


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] or sorted(MIGRATIONS.glob("*.sql"))
    errors = [e for f in files if f.suffix == ".sql" and f.exists() for e in check(f)]
    for err in errors:
        print(f"RLS check: {err}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
