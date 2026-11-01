import httpx
import pytest

from yai_scout.retrieval.tavily import TavilyClient, TavilyError, parse_search_payload


def test_parse_search_payload_uses_usage_credits():
    payload = {
        "results": [
            {"title": "T", "url": "https://a.com", "content": "c", "score": 0.5,
             "published_date": "2026-10-01"},
            {"title": "no url"},
        ],
        "usage": {"credits": 2},
    }
    results, credits = parse_search_payload(payload)
    assert len(results) == 1
    assert credits == 2.0
    assert results[0].title == "T"


def test_parse_search_payload_falls_back_to_depth_estimate():
    _, credits = parse_search_payload({"results": []}, depth="advanced")
    assert credits == 2.0


async def test_keyless_headers_and_request_shape():
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["mode"] = request.headers.get("x-tavily-access-mode")
        seen["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"results": [{"title": "T", "url": "https://a.com", "content": "c"}]},
        )

    client = TavilyClient("", transport=httpx.MockTransport(handler))
    results, credits = await client.search("hello")
    await client.aclose()
    assert results[0].url == "https://a.com"
    assert credits == 1.0
    assert seen["auth"] is None
    assert seen["mode"] == "keyless"
    assert '"query":"hello"' in (seen["body"] or "").replace(" ", "")


async def test_key_uses_bearer_header():
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"results": [], "usage": {"credits": 1}})

    client = TavilyClient("tvly-test", transport=httpx.MockTransport(handler))
    await client.search("q")
    await client.aclose()
    assert seen["auth"] == "Bearer tvly-test"


async def test_http_error_becomes_tavily_error_without_key_leak():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = TavilyClient("tvly-secret-key", transport=httpx.MockTransport(handler))
    with pytest.raises(TavilyError) as exc:
        await client.search("q")
    await client.aclose()
    assert exc.value.status_code == 429
    assert "tvly-secret-key" not in str(exc.value)
