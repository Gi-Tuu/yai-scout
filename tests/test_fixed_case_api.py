from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.store import Store

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {
    "answer": (
        "YAI Agent Core 当前版本是 0.24.0。"
        "来源：https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0"
    ),
    "as_of": "2026-11-01",
    "max_claims": 3,
    "mode": "replay",
}


def test_fixed_case_api_is_stale_without_url_claim(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        db_path=tmp_path / "fixed.sqlite3",
        snapshots_seed=str(ROOT / "benchmarks" / "snapshots.json"),
        tavily_api_key="",
        openai_api_key="",
        bifrost_base_url="",
        demo_limits_enabled=False,
    )
    store = Store(settings.db_path)
    app = create_app(settings=settings, store=store)
    with TestClient(app) as client:
        response = client.post("/freshness/verify", json=PAYLOAD)
        assert response.status_code == 200
        report = response.json()

    assert report["mode"] == "replay"
    assert len(report["claims"]) == 1
    assert report["claims"][0]["type"] == "version"
    assert "https://" not in report["claims"][0]["text"]
    assert report["verdicts"][0]["status"] == "stale"


class StableVersionTableTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return (
            [
                SearchResult(
                    title="Python End-of-Life Dates",
                    url="https://endoflife.date/python",
                    content="3.12 | 2023\n3.15 | latest",
                )
            ],
            0.0,
        )

    async def aclose(self) -> None:
        return None


def test_stable_release_claim_live_api_is_fresh(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        db_path=tmp_path / "stable.sqlite3",
        snapshots_seed=str(ROOT / "benchmarks" / "snapshots.json"),
        tavily_api_key="",
        openai_api_key="",
        bifrost_base_url="",
        demo_limits_enabled=False,
    )
    store = Store(settings.db_path)
    app = create_app(
        settings=settings, store=store, tavily=StableVersionTableTavily()
    )
    with TestClient(app) as client:
        response = client.post(
            "/freshness/verify",
            json={
                "answer": "Python 3.12 于 2023 年发布。",
                "as_of": "2026-11-01",
                "max_claims": 3,
                "mode": "live",
            },
        )
        assert response.status_code == 200
        report = response.json()

    assert report["mode"] == "live"
    assert report["verdicts"][0]["status"] == "fresh"
