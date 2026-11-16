"""A small stand-in for `psql "<url>" -c "<sql>"` (there is no Postgres install on this machine).

  uv run python scripts/psql.py "$DB_URL" -c "select 1"
  uv run python scripts/psql.py admin -c "select 1"     # `admin` / `api` / `system` = the .env URL
  echo "select 1" | uv run python scripts/psql.py admin  # SQL from stdin

Output looks like psql's (aligned table and "(N rows)", or the command tag such as
DELETE 0); errors print as "ERROR:  ..." and exit 1. Refuses anything that is not local
or a staging project in .claude/staging-targets.txt (core.targets), and production.
Each -c runs in autocommit, like psql.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

import psycopg  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

from core.targets import UnsafeTarget, check  # noqa: E402

ALIASES = {
    "admin": "DATABASE_URL_ADMIN",
    "api": "DATABASE_URL_API",
    "system": "DATABASE_URL_SYSTEM",
}


def _cell(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "t" if v else "f"
    return str(v)


def print_result(cur: psycopg.Cursor[tuple[object, ...]], tuples_only: bool) -> None:
    if cur.description is None:
        if not tuples_only:
            print(cur.statusmessage or "")
        return
    cols = [d.name for d in cur.description]
    rows = [[_cell(v) for v in r] for r in cur.fetchall()]
    if tuples_only:
        for r in rows:
            print("|".join(r))
        return
    widths = [max([len(c), *(len(r[i]) for r in rows)]) for i, c in enumerate(cols)]
    print(" " + " | ".join(c.center(w) for c, w in zip(cols, widths, strict=True)))
    print("-" + "-+-".join("-" * w for w in widths) + "-")
    for r in rows:
        print(" " + " | ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)))
    print(f"({len(rows)} row{'' if len(rows) == 1 else 's'})\n")


def main() -> int:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("url")
    p.add_argument("-c", dest="commands", action="append", default=[])
    p.add_argument("-t", dest="tuples_only", action="store_true")
    p.add_argument("-A", dest="unaligned", action="store_true")
    p.add_argument("-v", dest="vars", action="append", default=[])  # accepted, ignored
    args = p.parse_args()

    env = dotenv_values(ROOT / ".env")
    url = env.get(ALIASES[args.url], "") if args.url in ALIASES else args.url
    if not url:
        print(f"ERROR:  no URL for {args.url!r}", file=sys.stderr)
        return 2
    try:
        check(url, app_env=env.get("APP_ENV"))
    except UnsafeTarget as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 2

    commands = args.commands or [sys.stdin.read()]
    tuples_only = args.tuples_only or args.unaligned
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn:
            for sql in commands:
                cur = conn.execute(sql)  # type: ignore[call-overload]  # caller-supplied SQL by design
                print_result(cur, tuples_only)
    except psycopg.Error as err:
        print(f"ERROR:  {str(err).strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
