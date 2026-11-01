from __future__ import annotations

import httpx

from yai_scout.domain.models import Anchor
from yai_scout.sources.anchor import (
    host_allowed,
    live_anchor_result,
)


def _anchor(url: str = "https://docs.example.com/pricing") -> Anchor:
    return Anchor(id="a1", claim_key="k", url=url)


def test_host_allowlist_is_exact_and_https_only():
    allow = {"docs.example.com"}
    assert host_allowed("https://docs.example.com/pricing", allow)
    assert not host_allowed("https://evil-docs.example.com/pricing", allow)
    assert not host_allowed("http://docs.example.com/pricing", allow)


async def test_live_fetch_rejected_without_allowlist():
    result = await live_anchor_result(_anchor(), set())
    assert result is None


async def test_live_fetch_blocks_private_ip(monkeypatch):
    result = await live_anchor_result(
        _anchor(), {"docs.example.com"}, resolver=lambda host: None
    )
    assert result is None


async def test_live_fetch_happy_path_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><h1>Pricing</h1><p>1,000 credits</p></body></html>",
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await live_anchor_result(
        _anchor(),
        {"docs.example.com"},
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is not None
    assert "1,000 credits" in result.content
    assert result.content_hash

