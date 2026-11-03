from __future__ import annotations

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.store import Store


class CountingTavily:
    mode = "fake"
    authenticated = False

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, *args: object, **kwargs: object):
        self.calls += 1
        return [], 0.0

    async def aclose(self) -> None:
        return None


def test_public_synthetic_benchmark_does_not_call_tavily():
    tavily = CountingTavily()
    store = Store(":memory:")
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        scout_mode="all",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
        admin_token="secret",
    )
    app = create_app(settings=settings, tavily=tavily, store=store)  # type: ignore[arg-type]
    with TestClient(app) as client:
        response = client.post(
            "/api/benchmark/run",
            json={
                "agent_ids": ["mock_good"],
                "task_ids": ["a_stable_http_401", "b_python313_release_month"],
                "repeats": 2,
            },
        )
        assert response.status_code == 202
        session_id = response.json()["session"]["id"]
        for _ in range(200):
            data = client.get(f"/api/benchmark/sessions/{session_id}").json()
            if data["session"]["status"] != "running":
                break
        assert data["session"]["status"] == "done"
        assert tavily.calls == 0
        assert data["session"]["manifest"]["timeout_configuration"]["detect_freshness"] is False
    store.close()
