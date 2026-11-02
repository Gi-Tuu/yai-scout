from __future__ import annotations

import asyncio
import socket

import httpx

from yai_scout.domain.models import Anchor
from yai_scout.sources.anchor import (
    LIVE_MAX_BYTES,
    _read_capped,
    _resolve_public_ip,
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


async def test_live_fetch_blocks_private_ip():
    result = await live_anchor_result(
        _anchor(), {"docs.example.com"}, resolver=lambda host: None
    )
    assert result is None


async def test_private_or_mixed_dns_resolution_is_rejected(monkeypatch):
    def private(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]

    monkeypatch.setattr("yai_scout.sources.anchor.socket.getaddrinfo", private)
    assert _resolve_public_ip("docs.example.com") is None

    def mixed(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]

    monkeypatch.setattr("yai_scout.sources.anchor.socket.getaddrinfo", mixed)
    assert _resolve_public_ip("docs.example.com") is None


async def test_pinned_request_uses_original_host_and_sni():
    calls: list[httpx.Request] = []
    resolved: list[str] = []

    def resolver(host: str) -> str:
        resolved.append(host)
        return "93.184.216.34"

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<p>1,000 credits</p>",
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await live_anchor_result(
        _anchor(),
        {"docs.example.com"},
        client=client,
        resolver=resolver,
    )
    await client.aclose()
    assert result is not None
    assert resolved == ["docs.example.com"]  # resolved exactly once
    request = calls[0]
    assert request.url.scheme == "https"
    assert request.url.host == "93.184.216.34"
    assert request.headers["host"] == "docs.example.com"
    assert request.extensions["sni_hostname"] == "docs.example.com"


async def test_redirect_is_not_followed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://evil.example/"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await live_anchor_result(
        _anchor(),
        {"docs.example.com"},
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is None


async def test_non_text_content_type_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"credits": 1000}',
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await live_anchor_result(
        _anchor(),
        {"docs.example.com"},
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is None


async def test_timeout_returns_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<p>too late</p>",
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=0.05
    )
    result = await live_anchor_result(
        _anchor(),
        {"docs.example.com"},
        client=client,
        resolver=lambda host: "93.184.216.34",
        timeout_s=0.05,
    )
    await client.aclose()
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


async def test_read_capped_limits_body():
    response = httpx.Response(200, content=b"x" * (LIVE_MAX_BYTES + 100))
    data = await _read_capped(response)
    assert len(data) == LIVE_MAX_BYTES

