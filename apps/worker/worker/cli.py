"""Command-line helpers: `python -m worker.cli <command>`."""

from __future__ import annotations

import argparse
import sys
from uuid import UUID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m worker.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("heartbeat", help="Queue one heartbeat task on the broker")
    comp = sub.add_parser("compile", help="Compile one company's profile now (in this process)")
    comp.add_argument("tenant_id", type=UUID)
    sub.add_parser(
        "re-embed",
        help="Recompute every fingerprint and portfolio vector with the current embedding model",
    )
    fg = sub.add_parser("fetch-guard-report", help="Show the latest guarded-fetcher events")
    fg.add_argument("--last", type=int, default=5)
    rs = sub.add_parser("run-source", help="Run one source now, in this process")
    rs.add_argument("source_key")
    args = parser.parse_args(argv)

    if args.command == "heartbeat":
        from worker.tasks import heartbeat

        result = heartbeat.delay()
        print(f"queued heartbeat task {result.id}")
    elif args.command == "fetch-guard-report":
        from worker.ingest.enrich import report

        for row in report(args.last):
            when = f"{row['created_at']:%Y-%m-%d %H:%M:%S}"
            print(f"{when}  {row['outcome']:<8} {row['url']}  {row['reason'] or ''}")
    elif args.command == "run-source":
        import json

        from worker.ingest.runner import run_source

        print(json.dumps(run_source(args.source_key, "cli")))
    elif args.command == "compile":
        from worker import compiler

        print(compiler.compile_profile(args.tenant_id))
    elif args.command == "re-embed":
        from core.db import system_db_sync
        from worker import compiler

        with system_db_sync() as conn:
            tenants = [
                r["tenant_id"]
                for r in conn.execute(
                    "select tenant_id from public.tenant_profiles order by tenant_id"
                ).fetchall()
            ]
        for tenant_id in tenants:
            print(tenant_id, compiler.compile_profile(tenant_id, force=True))
        from worker import portfolio

        print("portfolio items re-embedded:", portfolio.re_embed_all())
    return 0


if __name__ == "__main__":
    sys.exit(main())
