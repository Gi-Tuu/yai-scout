from __future__ import annotations

import asyncio
import time

from httpx import ASGITransport, AsyncClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.domain.models import Anchor
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


async def test_slow_read_does_not_block_health(monkeypatch):
    store = Store(":memory:")
    store.save_anchor(
        Anchor(id="anc_1", claim_key="k", url="https://example.com", last_value="v")
    )
    original = store.list_anchors

    def slow_list_anchors(*args: object, **kwargs: object):
        time.sleep(0.3)
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "list_anchors", slow_list_anchors)
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
    )
    app = create_app(settings=settings, tavily=FakeTavily(), store=store)  # type: ignore[arg-type]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        started = time.perf_counter()
        slow_task = asyncio.create_task(client.get("/freshness/anchors"))
        await asyncio.sleep(0.03)
        health = await client.get("/api/healthz")
        health_elapsed = time.perf_counter() - started
        slow_response = await slow_task

    assert health.status_code == 200
    assert slow_response.status_code == 200
    assert health_elapsed < 0.2
    store.close()
