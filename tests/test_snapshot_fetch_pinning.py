from __future__ import annotations

import httpx

from yai_scout.sources.snapshot import fetch_text


async def test_fetch_text_pins_public_ip_and_host():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<p>page</p>",
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_text(
        "https://docs.example.com/page",
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is not None
    request = calls[0]
    assert request.url.scheme == "https"
    assert request.url.host == "93.184.216.34"
    assert request.headers["host"] == "docs.example.com"
    assert request.extensions["sni_hostname"] == "docs.example.com"
