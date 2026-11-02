from __future__ import annotations

import json

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


def test_app_end_to_end_routes_to_bifrost():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"claims":[{"text":"YAI Agent Core 当前版本是 0.24.0",'
                                '"type":"version","numbers":["0.24.0"],'
                                '"time_sensitive":true}]}'
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
        bifrost_base_url="http://127.0.0.1:8080/v1",
        bifrost_model="openai/deepseek-chat",
    )
    store = Store(":memory:")
    app = create_app(
        settings=settings,
        tavily=_FakeTavily(),
        store=store,  # type: ignore[arg-type]
        llm_transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        health = client.get("/api/healthz").json()
        assert health["llm"]["gateway"] == "bifrost"
        report = client.post(
            "/freshness/verify",
            json={
                "answer": "YAI Agent Core 当前版本是 0.24.0。",
                "as_of": "2026-11-01",
                "max_claims": 1,
                "mode": "replay",
            },
        )
        assert report.status_code == 200
    assert calls
    assert str(calls[0].url).endswith("/v1/chat/completions")
    assert json.loads(calls[0].content)["model"] == "openai/deepseek-chat"
    store.close()


def test_manifest_records_effective_bifrost_model_and_no_secret():
    from yai_scout.benchmark.dataset import load_dataset
    from yai_scout.benchmark.manifest import build_manifest, config_hash

    version, tasks = load_dataset()
    settings = Settings(
        _env_file=None,
        openai_api_key="sk-direct-secret",
        openai_base_url="https://api.deepseek.com",
        tavily_api_key="",
        bifrost_base_url="http://127.0.0.1:8080/v1",
        bifrost_api_key="sk-bifrost-secret",
        bifrost_model="openai/deepseek-chat",
    )
    manifest = build_manifest(
        experiment_id="exp_bifrost",
        dataset_version=version,
        tasks=tasks[:1],
        agents=[],
        cfg=settings,
        snapshot_ids=[],
        started_at="2026-11-02T00:00:00Z",
        policy_version="p",
        weights_version="w",
        agent_timeout_s=30,
        max_claims=2,
        detect_freshness=True,
    )
    assert manifest.model_name == "openai/deepseek-chat"
    assert manifest.tool_configuration["model_gateway"] == "bifrost"
    assert "sk-bifrost-secret" not in manifest.model_dump_json()
    assert "sk-direct-secret" not in manifest.model_dump_json()

    direct = settings.model_copy(
        update={"bifrost_base_url": "", "bifrost_model": "", "bifrost_api_key": ""}
    )
    direct_manifest = build_manifest(
        experiment_id="exp_direct",
        dataset_version=version,
        tasks=tasks[:1],
        agents=[],
        cfg=direct,
        snapshot_ids=[],
        started_at="2026-11-02T00:00:00Z",
        policy_version="p",
        weights_version="w",
        agent_timeout_s=30,
        max_claims=2,
        detect_freshness=True,
    )
    assert config_hash(manifest) != config_hash(direct_manifest)

