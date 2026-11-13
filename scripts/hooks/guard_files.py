"""PreToolUse hook for Edit/Write: keep secrets and applied migrations untouched.

Blocks (exit 2, reason on stderr, which Claude Code shows to the model):
  * .env files (except .env.example), key and certificate files, signing keys
  * any migration in supabase/migrations that git already tracks (= applied; write a new one)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
SECRET_NAMES = {"signing_keys.json", "id_rsa", "id_ed25519"}


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def reason_to_block(raw_path: str) -> str | None:
    path = Path(raw_path)
    name = path.name.lower()
    if (name == ".env" or name.startswith(".env.")) and name != ".env.example":
        return f"{raw_path}: .env files are never edited by Claude (CLAUDE.md). Ask the user."
    if name.endswith(SECRET_SUFFIXES) or name in SECRET_NAMES:
        return f"{raw_path}: key and certificate files are off limits."

    root = project_dir()
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[:2] == ("supabase", "migrations") and name.endswith(".sql"):
        tracked = subprocess.run(  # noqa: S603
            ["git", "ls-files", "--error-unmatch", rel.as_posix()],  # noqa: S607
            cwd=root,
            capture_output=True,
        )
        if tracked.returncode == 0:
            return (
                f"{rel.as_posix()} is committed, so it counts as applied. Applied migrations are "
                "never edited (CLAUDE.md): write a new migration instead."
            )
    return None


def main() -> int:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input") or {}
    paths = [tool_input.get(k) for k in ("file_path", "notebook_path", "path")]
    for p in filter(None, paths):
        reason = reason_to_block(str(p))
        if reason:
            print(f"Blocked by guard_files hook: {reason}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
