from __future__ import annotations

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.domain.models import DetectorReport
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def _app(store: Store, *, admin_token: str = ""):
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
        admin_token=admin_token,
    )
    return create_app(settings=settings, tavily=FakeTavily(), store=store)  # type: ignore[arg-type]


def _create_report(client: TestClient) -> str:
    response = client.post(
        "/freshness/verify",
        json={
            "answer": "Tavily 免费计划每月提供 1,000 credits。",
            "as_of": "2026-11-01",
            "max_claims": 1,
            "mode": "replay",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_report_is_not_readable_by_another_session():
    store = Store(":memory:")
    app = _app(store)
    with TestClient(app) as client_a, TestClient(app) as client_b:
        report_id = _create_report(client_a)
        assert client_a.get(f"/freshness/reports/{report_id}").status_code == 200
        assert client_b.get(f"/freshness/reports/{report_id}").status_code == 404
        assert client_b.get(f"/freshness/reports/{report_id}/export").status_code == 404
        assert client_b.get("/freshness/reports").json()["reports"] == []
        assert [
            item["id"]
            for item in client_a.get("/freshness/reports").json()["reports"]
        ] == [report_id]
    store.close()


def test_admin_can_read_report_from_another_session():
    store = Store(":memory:")
    app = _app(store, admin_token="secret")
    with TestClient(app) as client_a, TestClient(app) as client_b:
        report_id = _create_report(client_a)
        response = client_b.get(
            f"/freshness/reports/{report_id}",
            headers={"Authorization": "Bearer secret"},
        )
        assert response.status_code == 200
    store.close()


def test_research_task_is_scoped_to_session():
    store = Store(":memory:")
    app = _app(store)
    with TestClient(app) as client_a, TestClient(app) as client_b:
        created = client_a.post(
            "/api/research", json={"question": "Tavily credits pricing"}
        )
        assert created.status_code == 202
        task_id = created.json()["task"]["id"]
        assert client_a.get(f"/api/research/{task_id}").status_code == 200
        assert client_b.get(f"/api/research/{task_id}").status_code == 404
        assert all(
            item["id"] != task_id
            for item in client_b.get("/api/research").json()["tasks"]
        )
        assert any(
            item["id"] == task_id
            for item in client_a.get("/api/research").json()["tasks"]
        )
    store.close()


def test_owner_reports_are_not_crowded_out_by_other_sessions():
    store = Store(":memory:")
    for index in range(5):
        store.save_detector_report(
            DetectorReport(
                id=f"other_{index}",
                owner_id="other",
                answer="a",
                as_of="2026-11-01",
            )
        )
    store.save_detector_report(
        DetectorReport(
            id="mine",
            owner_id="me",
            answer="a",
            as_of="2026-11-01",
        )
    )
    reports = store.list_detector_reports(limit=3, owner_id="me")
    assert [report.id for report in reports] == ["mine"]
    store.close()
