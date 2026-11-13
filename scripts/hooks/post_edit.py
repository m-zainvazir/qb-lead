"""PostToolUse hook for Edit/Write: format and check the file that just changed.

  *.py                    -> ruff format, ruff check --fix, mypy
  apps/web/**/*.ts(x)     -> prettier, eslint, next typegen + tsc --noEmit
  supabase/migrations/*.sql -> scripts/check_migrations.py (RLS on every new table)

Problems are reported with exit 2 so Claude sees them at once.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
WEB = ROOT / "apps" / "web"


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    exe = shutil.which(cmd[0]) or cmd[0]
    proc = subprocess.run(  # noqa: S603
        [exe, *cmd[1:]], cwd=cwd, capture_output=True, text=True, timeout=180
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    data = json.load(sys.stdin)
    raw = (data.get("tool_input") or {}).get("file_path")
    if not raw:
        return 0
    path = Path(raw).resolve()
    try:
        rel = path.relative_to(ROOT.resolve())
    except ValueError:
        return 0
    if not path.exists() or "lead-gen-plans" in rel.parts or "node_modules" in rel.parts:
        return 0

    problems: list[str] = []
    if path.suffix == ".py":
        run(["uv", "run", "--no-sync", "ruff", "format", str(path)], ROOT)
        code, out = run(["uv", "run", "--no-sync", "ruff", "check", "--fix", str(path)], ROOT)
        if code:
            problems.append(out)
        if rel.parts[0] in ("apps", "packages") and "tests" not in rel.parts:
            code, out = run(["uv", "run", "--no-sync", "mypy"], ROOT)
            if code:
                problems.append(out)
    elif path.suffix in (".ts", ".tsx") and WEB in path.parents:
        run(["npx", "prettier", "--write", str(path)], WEB)
        code, out = run(["npx", "eslint", str(path)], WEB)
        if code:
            problems.append(out)
        code, out = run(["npm", "run", "--silent", "typecheck"], WEB)  # typegen + tsc
        if code:
            problems.append(out)
    elif path.suffix == ".sql" and rel.parts[:2] == ("supabase", "migrations"):
        code, out = run(["python", str(ROOT / "scripts" / "check_migrations.py"), str(path)], ROOT)
        if code:
            problems.append(out)

    if problems:
        print(
            f"post_edit checks failed for {rel.as_posix()}:\n" + "\n".join(problems),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
