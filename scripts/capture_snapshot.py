"""抓取一条证据快照（Wayback 历史 / 当前页面）。

用法：
    python scripts/capture_snapshot.py --url https://example.com --timestamp 20261001
    python scripts/capture_snapshot.py --url https://example.com --live

输出 snapshot id / origin / chars / sha；无历史存档时明确输出 NO_SNAPSHOT。
"""

from __future__ import annotations

import argparse
import asyncio

from yai_scout.config import ROOT, get_settings
from yai_scout.sources.snapshot import capture
from yai_scout.store import Store


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--timestamp", default=None, help="Wayback 时间戳，如 20261001")
    parser.add_argument("--live", action="store_true", help="抓当前页面（非历史）")
    args = parser.parse_args()

    settings = get_settings()
    store = Store(settings.db_path)
    snapshots_dir = ROOT / "data" / "snapshots"
    snapshot, text = await capture(
        store,
        url=args.url,
        snapshots_dir=snapshots_dir,
        timestamp=None if args.live else args.timestamp,
        origin="live" if args.live else "wayback",
    )
    if snapshot is None:
        print("NO_SNAPSHOT (no archive or fetch failed)")
        return 2
    print(
        f"snapshot={snapshot.id} origin={snapshot.origin} "
        f"chars={len(text or '')} sha={snapshot.content_hash[:16]}"
    )
    print(f"text_path={snapshot.text_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

