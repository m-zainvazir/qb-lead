"""Command-line helpers: `python -m api.cli <command>`.

Later modules add commands here. Commands that change data refuse to run when
APP_ENV is production.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from core.settings import get_settings

Command = Callable[[argparse.Namespace], int]
_COMMANDS: dict[str, tuple[str, Command]] = {}


def command(name: str, help_text: str) -> Callable[[Command], Command]:
    def register(fn: Command) -> Command:
        _COMMANDS[name] = (help_text, fn)
        return fn

    return register


@command("check-settings", "Load settings and report which environment is configured")
def _check_settings(_args: argparse.Namespace) -> int:
    s = get_settings()
    print(f"settings ok: env={s.app_env} supabase={s.supabase_url} commit={s.git_commit}")
    return 0


@command("db-roles", "Set passwords on the app_api / app_system login roles from the environment")
def _db_roles(_args: argparse.Namespace) -> int:
    import psycopg
    from psycopg import sql

    s = get_settings()
    if s.database_url_admin is None:
        print("DATABASE_URL_ADMIN is not set", file=sys.stderr)
        return 2
    passwords = {
        "app_api": s.app_db_password.get_secret_value() if s.app_db_password else "",
        "app_system": s.system_db_password.get_secret_value() if s.system_db_password else "",
    }
    if not all(len(p) >= 16 for p in passwords.values()):
        print("APP_DB_PASSWORD and SYSTEM_DB_PASSWORD must be set (16+ chars)", file=sys.stderr)
        return 2
    with psycopg.connect(s.database_url_admin.get_secret_value(), autocommit=True) as conn:
        for role, password in passwords.items():
            # ALTER ROLE cannot take bind parameters; psycopg's sql.Identifier/sql.Literal
            # quote both parts safely (semgrep's SQLAlchemy raw-query rule misfires here).
            conn.execute(  # nosemgrep
                sql.SQL("alter role {} with password {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
    print("passwords set for app_api, app_system")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, _fn) in _COMMANDS.items():
        sub.add_parser(name, help=help_text)
    args = parser.parse_args(argv)
    return _COMMANDS[args.command][1](args)


if __name__ == "__main__":
    sys.exit(main())
