from pathlib import Path

import httpx

from yai_scout.sources.snapshot import (
    html_to_text,
    save_snapshot,
    wayback_url,
)
from yai_scout.store import Store


def test_html_to_text_strips_scripts():
    html = (
        "<html><head><script>bad()</script></head>"
        "<body><h1>Tavily</h1><p>1,000 credits</p></body></html>"
    )
    text = html_to_text(html)
    assert "Tavily" in text
    assert "1,000 credits" in text
    assert "bad()" not in text


async def test_wayback_url_parses_availability():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "archived_snapshots": {
                    "closest": {
                        "available": True,
                        "url": "https://web.archive.org/web/20261001/https://example.com",
                    }
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    url = await wayback_url("https://example.com", "20261001", client=client)
    await client.aclose()
    assert url is not None and "web.archive.org" in url


async def test_wayback_url_returns_none_when_unavailable():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"archived_snapshots": {}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    url = await wayback_url("https://example.com", "20261001", client=client)
    await client.aclose()
    assert url is None


def test_save_snapshot_writes_file(tmp_path: Path):
    store = Store(":memory:")
    snapshot = save_snapshot(
        store,
        url="https://docs.tavily.com/documentation/api-credits",
        text="1,000 free API credits per month",
        origin="live",
        snapshots_dir=tmp_path,
    )
    assert snapshot.id.startswith("snap_")
    assert Path(snapshot.text_path).is_file()
    assert store.get_snapshot(snapshot.id) is not None
    store.close()

