"""Replay-only anchor evidence: read a stored snapshot by URL.

不访问网络，避免公开 API 把任意 URL 变成 SSRF 入口；live 锚点抓取需要 allowlist（未来）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..domain.models import Anchor
from ..retrieval.tavily import SearchResult
from ..store import Store


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


async def replay_anchor_result(
    store: Store, anchor: Anchor, target_time: str
) -> SearchResult | None:
    target = _parse(target_time)
    if target is None:
        return None
    candidates = []
    for snapshot in store.list_snapshots(limit=1000):
        if snapshot.url != anchor.url:
            continue
        published = _parse(snapshot.published_at)
        if published is None or published > target:
            continue
        candidates.append((published, snapshot))
    if not candidates:
        return None
    published, snapshot = max(candidates, key=lambda pair: pair[0])
    try:
        text = Path(snapshot.text_path).read_text(encoding="utf-8")
    except OSError:
        return None
    return SearchResult(
        title=snapshot.title or f"anchor snapshot {snapshot.id}",
        url=snapshot.url,
        content=text[:1200],
        score=1.0,
        published_date=snapshot.published_at,
    )
