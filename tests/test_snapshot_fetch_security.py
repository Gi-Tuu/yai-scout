from __future__ import annotations

import httpx

from yai_scout.sources.snapshot import MAX_FETCH_BYTES, fetch_text


async def test_fetch_text_rejects_private_and_non_http():
    assert await fetch_text("file:///etc/passwd") is None
    assert (
        await fetch_text("http://127.0.0.1/x", resolver=lambda host: "127.0.0.1")
        is None
    )


async def test_fetch_text_does_not_follow_redirect_to_private():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/private"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_text(
        "https://example.com/start",
        client=client,
        resolver=lambda host: "93.184.216.34" if "example.com" in host else "127.0.0.1",
    )
    await client.aclose()
    assert result is None
    assert len(calls) == 1


async def test_fetch_text_rejects_non_text_and_caps_body():
    def html(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="x" * 600_000)

    client = httpx.AsyncClient(transport=httpx.MockTransport(html))
    result = await fetch_text(
        "https://example.com/x",
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is not None
    assert len(result) <= MAX_FETCH_BYTES

    def binary(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

    client = httpx.AsyncClient(transport=httpx.MockTransport(binary))
    result = await fetch_text(
        "https://example.com/x",
        client=client,
        resolver=lambda host: "93.184.216.34",
    )
    await client.aclose()
    assert result is None
