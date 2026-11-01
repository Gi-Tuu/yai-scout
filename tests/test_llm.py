import httpx

from yai_scout.detector.extract_llm import extract_claims_llm
from yai_scout.llm import LLMClient


def _client(handler, *, key: str = "sk-test") -> LLMClient:
    return LLMClient(key, transport=httpx.MockTransport(handler))


async def test_chat_json_parses_plain_and_fenced_json():
    def plain(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"claims": []}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    client = _client(plain)
    result = await client.chat_json("sys", "user")
    await client.aclose()
    assert result is not None
    payload, meta = result
    assert payload == {"claims": []}
    assert meta.prompt_tokens == 10
    assert meta.cost_usd >= 0

    def fenced(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '```json\n{"ok": true}\n```'}}]},
        )

    client = _client(fenced)
    result = await client.chat_json("sys", "user")
    await client.aclose()
    assert result is not None
    assert result[0] == {"ok": True}


async def test_chat_json_without_key_returns_none():
    client = LLMClient("")
    assert client.available is False
    assert await client.chat_json("sys", "user") is None


async def test_chat_json_http_error_returns_none():
    client = _client(lambda _request: httpx.Response(401, json={"error": "bad key"}))
    assert await client.chat_json("sys", "user") is None


class FakeLLM:
    available = True

    def __init__(self, payload: dict | None) -> None:
        self.payload = payload

    async def chat_json(self, system: str, user: str, **kwargs):  # type: ignore[no-untyped-def]
        if self.payload is None:
            return None
        from yai_scout.llm import LLMResult

        return self.payload, LLMResult(
            text="{}", prompt_tokens=10, completion_tokens=5, cost_usd=0.001
        )


async def test_extract_claims_llm_validates_substrings():
    answer = "Tavily 免费计划每月提供 500 credits。版本是 1.2.3。"
    payload = {
        "claims": [
            {"text": "Tavily 免费计划每月提供 500 credits", "type": "pricing"},
            {"text": "模型编造的不存在句子", "type": "pricing"},
            {"text": "版本是 1.2.3", "type": "version"},
        ]
    }
    result = await extract_claims_llm(answer, FakeLLM(payload), max_claims=5)  # type: ignore[arg-type]
    assert result is not None
    claims, cost = result
    assert len(claims) == 2
    assert claims[0].numbers == ["500"]
    assert cost > 0


async def test_extract_claims_llm_returns_none_on_bad_payload():
    assert await extract_claims_llm("answer text", FakeLLM(None), max_claims=3) is None  # type: ignore[arg-type]

