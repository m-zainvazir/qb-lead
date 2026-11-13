"""Stop hook: run the fast unit tests so failures surface before Claude says "done"."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def main() -> int:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return 0  # already blocked once this turn; don't loop
    uv = shutil.which("uv") or "uv"
    proc = subprocess.run(  # noqa: S603
        [uv, "run", "--no-sync", "pytest", "-q", "-x", "-m", "not db", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode not in (0, 5):  # 5 = no tests collected
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-40:])
        print(f"Fast tests are failing; fix them before finishing:\n{tail}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
