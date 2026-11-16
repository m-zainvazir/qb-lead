# Sourced by the terminal test scripts (scripts/*_terminal_tests.sh). Not run directly.
#
# Loads .env.test.local (written by `make seed-test`), refuses anything that is not the
# local stack or a staging project listed in .claude/staging-targets.txt (never production),
# and gives the plans' `psql "<url>" -c "<sql>"` commands a stand-in (scripts/psql.py),
# since there is no Postgres install on this machine.

[ -f .env.test.local ] || { echo "Run 'make seed-test' first."; exit 2; }
# shellcheck disable=SC1091
source .env.test.local

uv run python -c '
import sys
sys.path.insert(0, "packages/core")
from core.targets import UnsafeTarget, check
try:
    print("target:", check(*sys.argv[1:]))
except UnsafeTarget as exc:
    sys.exit(f"Refusing: {exc}")
' "$SUPA" "$DB_URL" "$APP_DB_URL" || exit 2

psql() { uv run python scripts/psql.py "$@"; }
