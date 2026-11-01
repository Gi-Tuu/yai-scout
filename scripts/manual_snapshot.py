"""从本地 HTML/文本文件保存一份快照（用于手工存档的真实历史证据）。

用途：当 archive.org 不可达时，用户可自行在浏览器打开 Wayback 的历史页面并保存
HTML 到本地，再用本脚本入库；这样 replay 使用的仍是**真实历史页面**，不是伪造数据。

用法：
    python scripts/manual_snapshot.py --url https://example.com --file saved.html --published-at 2025-06-01
    python scripts/manual_snapshot.py --url https://example.com --text saved.txt --published-at 2025-06-01
"""

from __future__ import annotations

import argparse
from pathlib import Path

from yai_scout.config import ROOT, get_settings
from yai_scout.sources.snapshot import html_to_text, save_snapshot
from yai_scout.store import Store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--file", default="", help="保存的 HTML 文件")
    parser.add_argument("--text", default="", help="已抽取好的纯文本文件")
    parser.add_argument("--published-at", default=None)
    args = parser.parse_args()

    if not args.file and not args.text:
        print("需要 --file 或 --text")
        return 2
    if args.file:
        html = Path(args.file).read_text(encoding="utf-8", errors="ignore")
        text = html_to_text(html)
    else:
        text = Path(args.text).read_text(encoding="utf-8", errors="ignore")

    store = Store(get_settings().db_path)
    snapshot = save_snapshot(
        store,
        url=args.url,
        text=text,
        origin="manual",
        snapshots_dir=ROOT / "data" / "snapshots",
        published_at=args.published_at,
    )
    print(
        f"snapshot={snapshot.id} origin=manual chars={len(text)} "
        f"sha={snapshot.content_hash[:16]} path={snapshot.text_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
