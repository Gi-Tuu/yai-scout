import time

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, **kwargs) -> tuple[list[SearchResult], float]:
        self.calls += 1
        return (
            [
                SearchResult(
                    title=f"result {self.calls}",
                    url=f"https://site{self.calls}.example.com/a",
                    content="content",
                )
            ],
            1.0,
        )

    async def aclose(self) -> None:
        pass


def test_api_create_and_poll():
    store = Store(":memory:")
    app = create_app(
        settings=Settings(db_path=":memory:", max_queries=1),
        tavily=FakeTavily(),  # type: ignore[arg-type]
        store=store,
    )
    with TestClient(app) as client:
        health = client.get("/api/healthz")
        assert health.status_code == 200
        assert health.json()["tavily"]["mode"] == "fake"
        assert health.headers["x-content-type-options"] == "nosniff"
        assert "default-src 'self'" in health.headers["content-security-policy"]

        created = client.post("/api/research", json={"question": "test question"})
        assert created.status_code == 202
        task_id = created.json()["task"]["id"]

        body = {}
        for _ in range(200):
            body = client.get(f"/api/research/{task_id}").json()
            if body["task"]["status"] in {"delivered", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        assert body["task"]["status"] == "delivered"
        assert len(body["sources"]) >= 1
        assert body["plan"] is not None
        assert body["cost"]["credits"] >= 1
        assert body["event_count"] >= 3

        missing = client.get("/api/research/task_missing")
        assert missing.status_code == 404


def test_mode_guard_hides_disabled_app():
    app = create_app(
        settings=Settings(db_path=":memory:", max_queries=1, scout_mode="benchmark"),
        tavily=FakeTavily(),  # type: ignore[arg-type]
        store=Store(":memory:"),
    )
    with TestClient(app) as client:
        assert client.get("/benchmark").status_code == 200
        assert client.get("/freshness").status_code == 404
        assert client.get("/freshness/reports").status_code == 404

