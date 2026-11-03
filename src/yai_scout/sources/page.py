"""Controlled full-page fetch MVP.

Reuses the hardened live-anchor fetch (allowlist, pinned IP, Host/SNI,
no redirect, size/time cap) and marks the result as FETCHED_PAGE.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from ..domain.models import Anchor
from ..retrieval.tavily import SearchResult
from .anchor import live_anchor_result


async def fetch_page(
    url: str,
    allowlist: set[str],
    *,
    client: httpx.AsyncClient | None = None,
    resolver: Callable[[str], str | None] | None = None,
    timeout_s: float = 15.0,
) -> SearchResult | None:
    anchor = Anchor(id="page_fetch", claim_key="", url=url)
    return await live_anchor_result(
        anchor,
        allowlist,
        client=client,
        resolver=resolver,
        timeout_s=timeout_s,
    )
