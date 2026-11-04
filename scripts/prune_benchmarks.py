#!/usr/bin/env python
"""Prune old terminal benchmark sessions/results from the SQLite store."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from yai_scout.config import Settings
from yai_scout.store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="SQLite path (default: current settings)")
    parser.add_argument("--days", type=int, default=30, help="retention window in days")
    parser.add_argument("--dry-run", action="store_true", help="report without deleting")
    parser.add_argument(
        "--audit-dir",
        default=None,
        help="directory for pre-delete audit JSON (default: beside the DB)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    db_path = Path(args.db) if args.db else Settings().db_path
    store = Store(db_path)
    try:
        result = store.prune_benchmarks(
            days=args.days, dry_run=args.dry_run, audit_dir=args.audit_dir
        )
    finally:
        store.close()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"sessions={result['sessions']} results={result['results']} "
            f"skipped={result.get('skipped', 0)} "
            f"cutoff={result['cutoff']} dry_run={result['dry_run']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
