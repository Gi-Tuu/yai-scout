"""把 SQLite 中的快照导出为可入库的 JSON（用于打包进镜像/离线回放）。

用法：
    python scripts/export_snapshots.py
    python scripts/export_snapshots.py --out benchmarks/snapshots.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from yai_scout.config import ROOT, get_settings
from yai_scout.store import Store

DEFAULT_OUT = ROOT / "benchmarks" / "snapshots.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    store = Store(get_settings().db_path)
    snapshots = store.list_snapshots(limit=1000)
    payload = {"version": "snapshots/0.1", "snapshots": []}
    for snapshot in snapshots:
        try:
            text = Path(snapshot.text_path).read_text(encoding="utf-8")
        except OSError:
            continue
        payload["snapshots"].append(
            {
                "id": snapshot.id,
                "url": snapshot.url,
                "title": snapshot.title,
                "origin": snapshot.origin,
                "content_hash": snapshot.content_hash,
                "published_at": snapshot.published_at,
                "updated_at": snapshot.updated_at,
                "fetched_at": snapshot.fetched_at,
                "tier": snapshot.tier,
                "notes": snapshot.notes,
                "text": text,
            }
        )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"exported={len(payload['snapshots'])} file={out} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
