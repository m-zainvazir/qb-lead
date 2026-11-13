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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, _fn) in _COMMANDS.items():
        sub.add_parser(name, help=help_text)
    args = parser.parse_args(argv)
    return _COMMANDS[args.command][1](args)


if __name__ == "__main__":
    sys.exit(main())
