from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import httpx

from ..domain.models import Anchor
from ..retrieval.tavily import SearchResult
from .anchor import live_anchor_result


def merge_fetched_page(original: SearchResult, fetched: SearchResult) -> SearchResult:
    """Upgrade snippet content without losing source publication metadata."""
    return replace(
        fetched,
        title=original.title or fetched.title,
        url=original.url,
        score=original.score,
        published_date=(
            fetched.published_date
            if fetched.published_date is not None
            else original.published_date
        ),
        updated_date=fetched.updated_date or original.updated_date,
        published_date_source=(
            fetched.published_date_source
            if fetched.published_date is not None
            else original.published_date_source
        ),
        retrieved_at=fetched.retrieved_at or original.retrieved_at,
        content_hash=fetched.content_hash,
    )


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
