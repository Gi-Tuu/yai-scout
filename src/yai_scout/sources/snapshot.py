"""证据快照：Wayback 历史快照 / 当前页面抓取 + 落盘 + 入库。

原则：历史证据必须来自真实存档；没有快照就返回 None，由调用方标 simulated。
"""

from __future__ import annotations

import hashlib
import html.parser
import ipaddress
import re
import socket
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from ..domain.models import EvidenceSnapshot
from ..retrieval.quality import classify_source
from ..store import Store

WAYBACK_AVAILABLE = "https://archive.org/wayback/available"
DEFAULT_TIMEOUT = 30.0
MAX_FETCH_BYTES = 500_000
MAX_REDIRECTS = 3
TEXT_CONTENT_TYPES = ("text/html", "text/plain")


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


def _resolve_public_ip(
    host: str, resolver: Callable[[str], str | None] | None = None
) -> str | None:
    if resolver is not None:
        address = resolver(host)
        if not address:
            return None
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return None
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return None
        return address
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return None
    for info in infos:
        address = str(info[4][0])
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return None
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return None
    return str(infos[0][4][0]) if infos else None


def _public_ip_for(
    url: str, resolver: Callable[[str], str | None] | None = None
) -> tuple[str, str] | None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    host = parsed.hostname.lower()
    ip = _resolve_public_ip(host, resolver)
    if not ip:
        return None
    return host, ip


async def _read_capped(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        take = chunk[: MAX_FETCH_BYTES - total]
        if take:
            chunks.append(take)
            total += len(take)
        if total >= MAX_FETCH_BYTES:
            break
    return b"".join(chunks)


async def fetch_text(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    resolver: Callable[[str], str | None] | None = None,
) -> str | None:
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=False,
        trust_env=False,
    )
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            resolved = _public_ip_for(current, resolver)
            if resolved is None:
                return None
            host, ip = resolved
            ip_host = f"[{ip}]" if ":" in ip else ip
            parsed = urlsplit(current)
            pinned_url = f"https://{ip_host}{parsed.path or '/'}"
            if parsed.query:
                pinned_url += f"?{parsed.query}"
            request = client.build_request(
                "GET",
                pinned_url,
                headers={"Host": host},
                extensions={"sni_hostname": host},
            )
            resp = await client.send(request)
            try:
                if 300 <= resp.status_code < 400:
                    location = resp.headers.get("location")
                    if not location:
                        return None
                    current = urljoin(current, location)
                    continue
                if resp.status_code >= 400:
                    return None
                content_type = resp.headers.get("content-type", "").lower()
                if not any(item in content_type for item in TEXT_CONTENT_TYPES):
                    return None
                raw = await _read_capped(resp)
                return html_to_text(raw.decode("utf-8", errors="replace"))
            finally:
                await resp.aclose()
        return None
    except (httpx.HTTPError, ValueError, OSError):
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
    stored_path = snapshot_storage_path(store, text_path)
    tier, _ = classify_source(url)
    snapshot = EvidenceSnapshot(
        id=snapshot_id,
        url=url,
        title="",
        origin=origin,  # type: ignore[arg-type]
        content_hash=digest,
        raw_path="",
        text_path=stored_path,
        published_at=published_at,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        tier=tier,
        notes=f"{len(text)} chars",
    )
    return store.save_snapshot(snapshot)


def snapshot_storage_path(store: Store, text_path: Path) -> str:
    """Store paths relative to the DB directory when possible."""
    resolved = text_path.resolve()
    if store.path != ":memory:":
        try:
            return str(resolved.relative_to(Path(store.path).parent.resolve()))
        except ValueError:
            pass
    return str(resolved)


def resolve_snapshot_path(store: Store, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(store.path).parent.resolve() / path


def snapshot_eligible(snapshot: EvidenceSnapshot, target: datetime) -> bool:
    """Whether a snapshot can prove content at ``target``.

    Official release history and Wayback captures carry a historical proof time.
    Live/manual captures are only replay-eligible when both their capture and
    any observed update happened no later than the target.
    """
    published = _parse_snapshot_time(snapshot.published_at)
    updated = _parse_snapshot_time(snapshot.updated_at)
    fetched = _parse_snapshot_time(snapshot.fetched_at)
    if snapshot.origin in {"official_history", "wayback"}:
        if published is None or published > target:
            return False
        return updated is None or updated <= target
    if fetched is None or fetched > target:
        return False
    if updated is not None and updated > target:
        return False
    return published is None or published <= target


def _parse_snapshot_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


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
