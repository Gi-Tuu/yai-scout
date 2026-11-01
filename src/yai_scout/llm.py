"""OpenAI 兼容 LLM 客户端（DeepSeek / suanli 等）。

只做三件事：chat_json（结构化输出）、chat_text、用量/成本统计。
没有 key 时 available=False，调用方自动降级到规则版。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

# 价格量级（USD / 百万 token），仅用于成本估算；可按模型覆盖。
DEFAULT_INPUT_PRICE = 0.30
DEFAULT_OUTPUT_PRICE = 1.20

JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


@dataclass(slots=True)
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0


class LLMClient:
    def __init__(
        self,
        api_key: str = "",
        *,
        base_url: str = "https://api.suanli.cn/v1",
        model: str = "deepseek/deepseek-v4.1-flash-1017",
        timeout: float = 90.0,
        input_price: float = DEFAULT_INPUT_PRICE,
        output_price: float = DEFAULT_OUTPUT_PRICE,
        transport: httpx.AsyncBaseTransport | None = None,
        require_key: bool = True,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.input_price = input_price
        self.output_price = output_price
        self._transport = transport
        self._require_key = require_key
        self._client: httpx.AsyncClient | None = None

    @property
    def available(self) -> bool:
        return bool(self.api_key) or not self._require_key

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> LLMResult | None:
        if not self.available:
            return None
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.monotonic()
        try:
            client = await self._http()
            resp = await client.post(
                "/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except httpx.HTTPError:
            return None
        if resp.status_code >= 400:
            return None
        try:
            data = resp.json()
            choice = data["choices"][0]["message"]
            text = choice.get("content") or ""
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        cost = (
            prompt_tokens * self.input_price + completion_tokens * self.output_price
        ) / 1_000_000
        return LLMResult(
            text=text.strip(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=round(time.monotonic() - started, 3),
            cost_usd=round(cost, 6),
        )

    async def chat_text(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 600,
        temperature: float = 0.0,
    ) -> LLMResult | None:
        return await self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=False,
        )

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 900,
        temperature: float = 0.0,
    ) -> tuple[dict[str, Any], LLMResult] | None:
        result = await self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=True,
        )
        if result is None or not result.text:
            return None
        text = result.text
        fence = JSON_FENCE.search(text)
        if fence:
            text = fence.group(1)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        if not isinstance(payload, dict):
            return None
        return payload, result

