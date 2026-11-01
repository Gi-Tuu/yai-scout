"""证据快照：Wayback 历史快照 / 当前页面抓取 + 落盘 + 入库。

原则：历史证据必须来自真实存档；没有快照就返回 None，由调用方标 simulated。
"""

from __future__ import annotations

import hashlib
import html.parser
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ..domain.models import EvidenceSnapshot
from ..retrieval.quality import classify_source
from ..store import Store

WAYBACK_AVAILABLE = "https://archive.org/wayback/available"
DEFAULT_TIMEOUT = 30.0


class _TextExtractor(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "\n".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def wayback_url(
    url: str, timestamp: str, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """查询 Wayback 是否有该时间点附近的快照；返回存档 URL 或 None。"""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    try:
        resp = await client.get(
            WAYBACK_AVAILABLE, params={"url": url, "timestamp": timestamp}
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        closest = (data.get("archived_snapshots") or {}).get("closest") or {}
        if not closest.get("available"):
            return None
        return str(closest.get("url") or "")
    except httpx.HTTPError:
        return None
    finally:
        if owns_client:
            await client.aclose()


async def fetch_text(url: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
    try:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return None
        return html_to_text(resp.text)
    except httpx.HTTPError:
        return None
    finally:
        if owns_client:
            await client.aclose()


def save_snapshot(
    store: Store,
    *,
    url: str,
    text: str,
    origin: str,
    snapshots_dir: Path,
    published_at: str | None = None,
) -> EvidenceSnapshot:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    snapshot_id = f"snap_{digest[:12]}"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    text_path = snapshots_dir / f"{snapshot_id}.txt"
    text_path.write_text(text, encoding="utf-8")
    tier, _ = classify_source(url)
    snapshot = EvidenceSnapshot(
        id=snapshot_id,
        url=url,
        title="",
        origin=origin,  # type: ignore[arg-type]
        content_hash=digest,
        raw_path="",
        text_path=str(text_path),
        published_at=published_at,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        tier=tier,
        notes=f"{len(text)} chars",
    )
    return store.save_snapshot(snapshot)


async def capture(
    store: Store,
    *,
    url: str,
    snapshots_dir: Path,
    timestamp: str | None = None,
    origin: str = "wayback",
) -> tuple[EvidenceSnapshot | None, str | None]:
    """抓取历史/当前快照；历史无存档时返回 (None, None)。"""
    if timestamp:
        archived = await wayback_url(url, timestamp)
        if not archived:
            return None, None
        text = await fetch_text(archived)
        if not text:
            return None, None
        snapshot = save_snapshot(
            store,
            url=url,
            text=text,
            origin=origin,
            snapshots_dir=snapshots_dir,
            published_at=timestamp,
        )
        return snapshot, text
    text = await fetch_text(url)
    if not text:
        return None, None
    return save_snapshot(
        store, url=url, text=text, origin="live", snapshots_dir=snapshots_dir
    ), text


def new_id(prefix: str = "snap") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"
