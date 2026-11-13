"""Create a migration for a new tenant table from supabase/templates/tenant_table.sql.

python scripts/new_tenant_table.py leads      (or: make migration-tenant name=leads)
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "supabase" / "templates" / "tenant_table.sql"
MIGRATIONS = ROOT / "supabase" / "migrations"


def render(table: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,50}", table):
        raise ValueError("table name must be lower_snake_case, 2-51 characters")
    return TEMPLATE.read_text(encoding="utf-8").replace("__TABLE__", table)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    table = argv[0]
    try:
        sql = render(table)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    out = MIGRATIONS / f"{stamp}_create_{table}.sql"
    out.write_text(sql, encoding="utf-8", newline="\n")
    print(out.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
