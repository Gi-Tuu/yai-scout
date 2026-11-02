"""Read-only SQLite payload/column consistency check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from yai_scout.store import Store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    store = Store(Path(args.db))
    try:
        issues = store.consistency_report()
    finally:
        store.close()
    print(json.dumps({"issues": issues, "count": len(issues)}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
