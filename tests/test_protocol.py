import httpx
import pytest

from yai_scout.benchmark.adapters import HttpAdapter
from yai_scout.benchmark.dataset import load_tasks
from yai_scout.benchmark.protocol import (
    PROTOCOL_VERSION,
    validate_run_response,
)


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/manifest":
            return httpx.Response(
                200,
                json={
                    "protocol_version": PROTOCOL_VERSION,
                    "agent_id": "ext",
                    "agent_version": "1.0.0",
                    "framework": "custom",
                    "models": [],
                    "tools": [],
                    "capabilities": {},
                },
            )
        if request.url.path == "/run":
            return httpx.Response(
                200,
                json={
                    "protocol_version": PROTOCOL_VERSION,
                    "answer": "Tavily gives 1,000 credits [1].",
                    "citations": ["https://docs.tavily.com/documentation/api-credits"],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 20,
                        "model": "ext-model",
                        "provider": "ext",
                    },
                    "cost": {
                        "estimated_usd": 0.001,
                        "price_table_version": "2026-11-01",
                        "estimated": True,
                    },
                    "latency_ms": 800,
                    "trace": [{"step": "search"}],
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_http_adapter_implements_protocol():
    adapter = HttpAdapter("ext", "External", "http://agent.local", transport=_transport())
    manifest = await adapter.manifest()
    assert manifest.agent_id == "ext"

    task = load_tasks()[3]  # b_tavily_free_credits
    answer = await adapter.answer(task)
    assert answer.text.startswith("Tavily")
    assert answer.citations
    assert answer.prompt_tokens == 120 and answer.completion_tokens == 20
    assert answer.tokens == 140
    assert answer.model == "ext-model"
    assert answer.cost_usd == 0.001


def test_validate_run_response_rejects_wrong_version():
    with pytest.raises(ValueError):
        validate_run_response(
            {
                "protocol_version": "scout-adapter/0.9",
                "answer": "x",
            }
        )
