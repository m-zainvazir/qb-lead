"""Command-line helpers: `python -m worker.cli <command>`."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m worker.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("heartbeat", help="Queue one heartbeat task on the broker")
    args = parser.parse_args(argv)

    if args.command == "heartbeat":
        from worker.tasks import heartbeat

        result = heartbeat.delay()
        print(f"queued heartbeat task {result.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
