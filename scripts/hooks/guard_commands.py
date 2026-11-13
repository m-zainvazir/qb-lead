"""PreToolUse hook for shell commands: one typo cannot wipe a real database.

Blocks (exit 2):
  * `supabase db reset` unless it targets the local stack (`--local`, no --linked/--db-url)
  * `supabase db push`, `supabase link` (remote projects are changed by CI/deploys, not here)
  * DROP TABLE / SCHEMA / DATABASE / ROLE and TRUNCATE
  * writing to .env files from the shell
  * anything that names a protected target listed in .claude/protected-targets.txt
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bsupabase\s+db\s+reset\b(?![^\n;&|]*--local)", re.I),
        "`supabase db reset` without --local. Use `make db-reset` (local only).",
    ),
    (
        re.compile(r"\bsupabase\s+db\s+reset\b[^\n;&|]*(--linked|--db-url)", re.I),
        "`supabase db reset` against a linked or remote database.",
    ),
    (
        re.compile(r"\bsupabase\s+(db\s+push|link)\b", re.I),
        "pushing to or linking a remote project.",
    ),
    (
        re.compile(r"\bdrop\s+(table|schema|database|role|owned)\b", re.I),
        "a DROP statement. Write a migration and let the user apply it.",
    ),
    (re.compile(r"\btruncate\b", re.I), "a TRUNCATE statement."),
    (
        re.compile(r"(>>?|\btee\b(\s+-a)?)\s*[\"']?[^\s\"']*\.env(\.[\w.-]+)?[\"']?(\s|$)", re.I),
        "writing to a .env file.",
    ),
    (
        re.compile(r"\b(sed|perl)\s+-i\S*\s[^\n;&|]*\.env\b", re.I),
        "editing a .env file in place.",
    ),
]


def protected_targets() -> list[str]:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    f = root / ".claude" / "protected-targets.txt"
    if not f.exists():
        return []
    return [
        line.strip()
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def reason_to_block(command: str) -> str | None:
    for pattern, why in RULES:
        if pattern.search(command):
            return why
    lowered = command.lower()
    for target in protected_targets():
        if target.lower() in lowered:
            return f"the command names a protected target ({target})."
    return None


def main() -> int:
    data = json.load(sys.stdin)
    command = str((data.get("tool_input") or {}).get("command", ""))
    reason = reason_to_block(command)
    if reason:
        print(
            f"Blocked by guard_commands hook: {reason} If this is really intended, ask the user "
            "to run it themselves.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
