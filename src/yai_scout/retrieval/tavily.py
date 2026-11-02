"""Tavily 检索适配器（REST，不依赖 CLI）。

- 有 TAVILY_API_KEY 时走 Bearer 鉴权；没有且允许 keyless 时用
  `X-Tavily-Access-Mode: keyless`（有限速）。
- 只做检索与结果解析，不做证据抽取；credits 记到调用方（Director）。
- 绝不把 key 写进日志/异常信息。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

from ..domain.models import EvidenceKind, utcnow_iso

# 官方计价：basic=1、advanced=2（credit/次）；缺失 usage 时按此估算。
DEPTH_CREDITS = {"basic": 1.0, "advanced": 2.0}


class TavilyError(RuntimeError):
    """Tavily 调用失败。message 中不含凭据。"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: str | None = None
    retrieved_at: str = ""
    content_hash: str = ""
    evidence_kind: EvidenceKind = EvidenceKind.SEARCH_SNIPPET
    fetch_status: str = "snippet"


def estimate_credits(depth: str) -> float:
    return DEPTH_CREDITS.get(depth, 1.0)


def parse_search_payload(
    payload: dict[str, Any], *, depth: str = "basic"
) -> tuple[list[SearchResult], float]:
    """把 Tavily /search 响应解析成 SearchResult 列表 + credits 消耗。"""
    raw_results = payload.get("results") or []
    results: list[SearchResult] = []
    for item in raw_results:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        content = str(item.get("content") or "").strip()
        results.append(
            SearchResult(
                title=str(item.get("title") or "").strip(),
                url=url,
                content=content,
                score=float(item.get("score") or 0.0),
                published_date=item.get("published_date"),
                retrieved_at=utcnow_iso(),
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
        )
    usage = payload.get("usage") or {}
    credits = usage.get("credits")
    return results, float(credits) if credits is not None else estimate_credits(depth)


class TavilyClient:
    def __init__(
        self,
        api_key: str = "",
        *,
        base_url: str = "https://api.tavily.com",
        allow_keyless: bool = True,
        timeout: float = 30.0,
        search_depth: str = "basic",
        max_results: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.allow_keyless = allow_keyless
        self.timeout = timeout
        self.search_depth = search_depth
        self.max_results = max_results
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.api_key)

    @property
    def mode(self) -> str:
        return "key" if self.authenticated else "keyless"

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

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.authenticated:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.allow_keyless:
            headers["X-Tavily-Access-Mode"] = "keyless"
        else:
            raise TavilyError("未配置 TAVILY_API_KEY，且 keyless 模式已关闭")
        return headers

    async def search(
        self,
        query: str,
        *,
        depth: str | None = None,
        max_results: int | None = None,
    ) -> tuple[list[SearchResult], float]:
        depth = depth or self.search_depth
        body = {
            "query": query,
            "search_depth": depth,
            "max_results": max_results or self.max_results,
            "include_answer": False,
            "include_raw_content": False,
            # 证据需要发布时间：让 Tavily 尽量返回 published_date（不额外计费）
            "include_published_date": True,
        }
        client = await self._http()
        try:
            resp = await client.post("/search", json=body, headers=self._headers())
        except httpx.HTTPError as exc:
            raise TavilyError(f"网络错误: {type(exc).__name__}") from None
        if resp.status_code >= 400:
            # 不回显请求头；仅保留状态码与服务端错误前缀
            detail = resp.text[:200].replace("\n", " ")
            raise TavilyError(f"HTTP {resp.status_code}: {detail}", status_code=resp.status_code)
        data = resp.json()
        if not isinstance(data, dict):
            raise TavilyError("响应格式异常：不是 JSON object")
        return parse_search_payload(data, depth=depth)

