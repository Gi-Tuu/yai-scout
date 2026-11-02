from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def _app(**overrides: object):
    values: dict[str, object] = {
        "_env_file": None,
        "db_path": ":memory:",
        "openai_api_key": "",
        "tavily_api_key": "",
        "rate_limit_per_minute": 1,
        "daily_detector_limit": 10,
        "daily_benchmark_limit": 10,
        "public_anchor_writes": True,
    }
    values.update(overrides)
    settings = Settings(**values)  # type: ignore[arg-type]
    return create_app(settings=settings, tavily=FakeTavily(), store=Store(":memory:"))


def _detect(client: TestClient) -> int:
    return client.post(
        "/api/detector",
        json={"answer": "The price is 10 dollars today.", "max_claims": 1},
    ).status_code


def test_per_ip_per_minute_limit():
    app = _app()
    with TestClient(app) as client:
        assert _detect(client) == 200
        blocked = client.post(
            "/api/detector",
            json={"answer": "The price is 10 dollars today.", "max_claims": 1},
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) >= 1


def test_global_per_minute_limit_across_ips():
    app = _app(rate_limit_per_minute=1, daily_detector_limit=10)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/detector",
                json={"answer": "The price is 10 dollars today.", "max_claims": 1},
                headers={"X-Forwarded-For": "203.0.113.10"},
            ).status_code
            == 200
        )
        blocked = client.post(
            "/api/detector",
            json={"answer": "The price is 10 dollars today.", "max_claims": 1},
            headers={"X-Forwarded-For": "203.0.113.11"},
        )
        assert blocked.status_code == 429


def test_daily_limit_blocks_even_with_new_ip():
    app = _app(rate_limit_per_minute=100, daily_detector_limit=1)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/detector",
                json={"answer": "The price is 10 dollars today.", "max_claims": 1},
                headers={"X-Forwarded-For": "203.0.113.1"},
            ).status_code
            == 200
        )
        blocked = client.post(
            "/api/detector",
            json={"answer": "The price is 10 dollars today.", "max_claims": 1},
            headers={"X-Forwarded-For": "203.0.113.2"},
        )
        assert blocked.status_code == 429
        assert "rate limit" in blocked.json()["detail"]


def test_cost_guard_can_be_disabled_for_tests():
    app = _app(demo_limits_enabled=False, rate_limit_per_minute=1)
    with TestClient(app) as client:
        assert _detect(client) == 200
        assert _detect(client) == 200


def test_healthz_exposes_usage():
    app = _app()
    with TestClient(app) as client:
        assert _detect(client) == 200
        limits = client.get("/api/healthz").json()["limits"]
        assert limits["daily_used"]["detector"] == 1
        assert limits["daily_limit"]["detector"] == 10

def test_anchor_creation_is_rate_limited():
    app = _app(rate_limit_per_minute=1)
    body = {
        "claim_text": "Tavily 免费计划每月提供 1,000 credits",
        "url": "https://docs.tavily.com/documentation/api-credits",
        "last_value": "1000",
        "source_tier": 1,
    }
    with TestClient(app) as client:
        assert client.post("/freshness/anchors", json=body).status_code == 201
        blocked = client.post("/freshness/anchors", json=body)
        assert blocked.status_code == 429
        assert "anchor" in blocked.json()["detail"]

def _research(client: TestClient) -> int:
    return client.post(
        "/api/research",
        json={"question": "Tavily credits pricing"},
    ).status_code


def test_research_endpoint_is_rate_limited():
    app = _app(rate_limit_per_minute=1)
    with TestClient(app) as client:
        assert _research(client) == 202
        blocked = client.post(
            "/api/research",
            json={"question": "Tavily credits pricing"},
        )
        assert blocked.status_code == 429
        assert "research" in blocked.json()["detail"]


def test_research_can_be_disabled():
    app = _app(research_enabled=False)
    with TestClient(app) as client:
        assert _research(client) == 404


def test_research_active_task_cap():
    app = _app(rate_limit_per_minute=10, max_active_research_tasks=0)
    with TestClient(app) as client:
        response = client.post(
            "/api/research",
            json={"question": "Tavily credits pricing"},
        )
        assert response.status_code == 429
        assert "active research" in response.json()["detail"]

