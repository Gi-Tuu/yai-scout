from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.llm import LLMClient
from yai_scout.store import Store


async def test_llm_client_routes_to_bifrost_without_key():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok":true}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    client = LLMClient(
        "",
        base_url="http://127.0.0.1:8080/v1",
        model="openai/deepseek-chat",
        transport=httpx.MockTransport(handler),
        require_key=False,
    )
    assert client.available is True
    parsed = await client.chat_json("system", "user")
    assert parsed is not None
    payload, result = parsed
    assert payload == {"ok": True}
    assert result.prompt_tokens == 10
    assert str(calls[0].url) == "http://127.0.0.1:8080/v1/chat/completions"
    assert calls[0].headers["content-type"] == "application/json"
    assert "authorization" not in calls[0].headers
    await client.aclose()


def test_bifrost_settings_are_optional():
    cfg = Settings(
        _env_file=None,
        openai_api_key="",
        bifrost_base_url="http://127.0.0.1:8080/v1",
        bifrost_model="openai/deepseek-chat",
    )
    assert cfg.bifrost_base_url.endswith("/v1")
    assert cfg.bifrost_model == "openai/deepseek-chat"


@pytest.mark.parametrize("base", ["http://127.0.0.1:8080/v1", "http://bifrost:8080/v1"])
def test_bifrost_base_url_forms(base: str):
    assert base.startswith("http://")



class _FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def test_healthz_reports_bifrost_gateway():
    store = Store(":memory:")
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
        bifrost_base_url="http://127.0.0.1:8080/v1",
        bifrost_model="openai/deepseek-chat",
    )
    app = create_app(settings=settings, tavily=_FakeTavily(), store=store)  # type: ignore[arg-type]
    with TestClient(app) as client:
        health = client.get("/api/healthz").json()
        assert health["llm"]["gateway"] == "bifrost"
        assert health["llm"]["model"] == "openai/deepseek-chat"
    store.close()

