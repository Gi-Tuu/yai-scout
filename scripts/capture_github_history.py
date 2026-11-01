"""抓取 GitHub Releases 作为真实历史快照（官方历史，非 Wayback）。

用途：为 replay 提供真实历史证据（每条 release 一个快照，published_at=官方发布时间）。
用法：
    python scripts/capture_github_history.py --repo Gi-Tuu/yai-agent-core
    python scripts/capture_github_history.py --repo maximhq/bifrost --limit 10
"""

from __future__ import annotations

import argparse
import asyncio

from yai_scout.config import ROOT, get_settings
from yai_scout.sources.github_history import capture_github_releases
from yai_scout.store import Store


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    store = Store(get_settings().db_path)
    snapshots = await capture_github_releases(
        store,
        args.repo,
        snapshots_dir=ROOT / "data" / "snapshots",
        max_releases=args.limit,
    )
    print(f"captured={len(snapshots)}")
    for snapshot in snapshots[:10]:
        print(
            f"  {snapshot.id} {snapshot.published_at} {snapshot.url} "
            f"({snapshot.notes})"
        )
    return 0 if snapshots else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
