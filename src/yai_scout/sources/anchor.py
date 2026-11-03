"""Replay-only and optional live anchor evidence.

Live fetching is intentionally conservative: HTTPS only, exact host allowlist,
public-IP check, no redirects, no cookies/auth, size/time limits. It is disabled
by default and must be enabled explicitly; this is not a general URL fetcher.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..domain.models import Anchor, EvidenceKind
from ..retrieval.tavily import SearchResult
from ..store import Store
from .snapshot import html_to_text

LIVE_MAX_BYTES = 500_000
LIVE_TIMEOUT_S = 15.0


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def host_allowed(url: str, allowlist: set[str]) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and (parts.hostname or "").lower() in allowlist


def _resolve_public_ip(host: str) -> str | None:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return None
    public: list[str] = []
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
        public.append(address)
    return public[0] if public else None


async def replay_anchor_result(
    store: Store, anchor: Anchor, target_time: str
) -> SearchResult | None:
    target = _parse(target_time)
    if target is None:
        return None
    candidates = []
    offset = 0
    while True:
        snapshots = await asyncio.to_thread(
            store.list_snapshots_for_url_page, anchor.url, offset, 500
        )
        if not snapshots:
            break
        for snapshot in snapshots:
            published = _parse(snapshot.published_at)
            if published is None or published > target:
                continue
            candidates.append((published, snapshot))
        offset += len(snapshots)
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
        retrieved_at=snapshot.fetched_at,
        content_hash=snapshot.content_hash,
        evidence_kind=EvidenceKind.ARCHIVED_SOURCE,
        fetch_status="snapshot",
    )


async def _read_capped(response: httpx.Response) -> bytes:
    """Read at most LIVE_MAX_BYTES from a (possibly streaming) response."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        take = chunk[: LIVE_MAX_BYTES - total]
        if take:
            chunks.append(take)
            total += len(take)
        if total >= LIVE_MAX_BYTES:
            break
    return b"".join(chunks)


async def live_anchor_result(
    anchor: Anchor,
    allowlist: set[str],
    *,
    client: httpx.AsyncClient | None = None,
    resolver: Callable[[str], str | None] | None = None,
    timeout_s: float = LIVE_TIMEOUT_S,
) -> SearchResult | None:
    if not host_allowed(anchor.url, allowlist):
        return None
    host = (urlsplit(anchor.url).hostname or "").lower()
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=timeout_s,
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "yai-scout-anchor/1.0"},
    )
    response: httpx.Response | None = None
    try:
        async def _get_response() -> httpx.Response | None:
            if client is not None and not owns_client and resolver is None:
                # Injected client without resolver (MockTransport tests).
                return await client.get(anchor.url)
            ip = (resolver or _resolve_public_ip)(host)
            if not ip:
                return None
            parsed = urlsplit(anchor.url)
            ip_host = f"[{ip}]" if ":" in ip else ip
            pinned_url = f"https://{ip_host}{parsed.path or '/'}"
            if parsed.query:
                pinned_url += f"?{parsed.query}"
            request = client.build_request(
                "GET",
                pinned_url,
                headers={"Host": host},
                extensions={"sni_hostname": host},
            )
            return await client.send(request, stream=True)

        response = await asyncio.wait_for(_get_response(), timeout=timeout_s)
        if response is None or response.status_code != 200:
            return None
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None
        raw = await asyncio.wait_for(_read_capped(response), timeout=timeout_s)
        text = html_to_text(raw.decode("utf-8", errors="replace"))
        if not text.strip():
            return None
        return SearchResult(
            title=f"anchor live {host}",
            url=anchor.url,
            content=text[:1200],
            score=1.0,
            published_date=None,  # retrieval time is not publication time
            retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            evidence_kind=EvidenceKind.FETCHED_PAGE,
            fetch_status="ok",
        )
    except (httpx.HTTPError, TimeoutError):
        return None
    finally:
        if response is not None:
            await response.aclose()
        if owns_client:
            await client.aclose()
