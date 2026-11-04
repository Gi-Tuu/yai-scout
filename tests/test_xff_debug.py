from __future__ import annotations

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.store import Store


def _app(token: str) -> TestClient:
    app = create_app(
        settings=Settings(
            _env_file=None,
            db_path=":memory:",
            openai_api_key="",
            tavily_api_key="",
            xff_debug_token=token,
        ),
        store=Store(":memory:"),
    )
    return TestClient(app)


def test_xff_debug_requires_token() -> None:
    with _app("dbg-token") as client:
        assert client.get("/admin/debug/request").status_code == 401
        assert client.get(
            "/admin/debug/request", headers={"X-XFF-Debug": "wrong"}
        ).status_code == 401


def test_xff_debug_returns_last_hop() -> None:
    with _app("dbg-token") as client:
        response = client.get(
            "/admin/debug/request",
            headers={
                "X-XFF-Debug": "dbg-token",
                "X-Forwarded-For": "198.51.100.10, 203.0.113.20",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["resolved_client_key"] == "203.0.113.20"
        assert payload["x_forwarded_for_chain"] == ["198.51.100.10", "203.0.113.20"]


def test_xff_debug_disabled_without_token() -> None:
    with _app("") as client:
        assert client.get("/admin/debug/request").status_code == 404
