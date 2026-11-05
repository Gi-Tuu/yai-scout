from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.detector.verify import build_query
from yai_scout.domain.models import Claim, ClaimType
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def _app() -> tuple[TestClient, Store]:
    store = Store(":memory:")
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
    )
    app = create_app(settings=settings, tavily=FakeTavily(), store=store)  # type: ignore[arg-type]
    return TestClient(app), store


def test_query_year_follows_as_of():
    claim = Claim(
        id="c", text="Tavily 免费计划每月提供 500 credits", type=ClaimType.PRICING
    )
    assert "latest official 2027" in build_query(claim, "2027-01-01")
    assert "latest official 2026" not in build_query(claim, "2027-01-01")


def test_replay_requires_explicit_as_of():
    client, store = _app()
    with client:
        response = client.post(
            "/freshness/verify",
            json={
                "answer": "Tavily 免费计划每月提供 500 credits。",
                "mode": "replay",
            },
        )
        assert response.status_code == 400
        assert "as_of" in response.json()["detail"]
    store.close()


def test_invalid_as_of_is_rejected():
    client, store = _app()
    with client:
        response = client.post(
            "/freshness/verify",
            json={
                "answer": "Tavily 免费计划每月提供 500 credits。",
                "as_of": "not-a-date",
            },
        )
        assert response.status_code == 400
    store.close()


def test_live_mode_uses_current_date_when_as_of_absent():
    client, store = _app()
    with client:
        response = client.post(
            "/api/detector",
            json={"answer": "Tavily 免费计划每月提供 500 credits。"},
        )
        assert response.status_code == 200
        report = response.json()
        assert report["as_of"].startswith(datetime.now(UTC).date().isoformat())
        assert "T" in report["as_of"]
    store.close()
