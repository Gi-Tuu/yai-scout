"""Agent 适配器：统一「问题 → 答案 + 引用 + 成本」协议。"""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx

from ..domain.models import AgentAnswer, BenchmarkTask
from ..llm import LLMClient
from ..pipeline.planning import build_plan
from ..retrieval.tavily import SearchResult, TavilyClient

# demo 用的"过期知识"：用于展示 detector 与排行榜的差异
STALE_VALUES: dict[str, str] = {
    "tavily_free_credits": "500",
    "tavily_student_plan": "2000",
    "tavily_paygo_price": "0.010",
    "deepseek_flash_input_price": "0.15",
    "claude_haiku_output_price": "0.40",
    "bifrost_port": "8000",
    "yai_version": "0.24.0",
    "geekroom_deadline": "2026-11-22",
    "omnidimension_free": "10",
}


class AgentAdapter(Protocol):
    id: str
    name: str
    description: str

    async def answer(self, task: BenchmarkTask) -> AgentAnswer: ...


class MockAdapter:
    """合成适配器：good=按金标回答；stale=用旧值回答。只用于 demo/回归。"""

    def __init__(self, agent_id: str, name: str, *, good: bool = True) -> None:
        self.id = agent_id
        self.name = name
        self.description = "synthetic adapter for demo (no network)"
        self.good = good

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        topic = task.question.rstrip("？? ").strip()
        if self.good:
            value = task.gold_values[0] if task.gold_values else "unknown"
            text = f"{topic} 为 {value}。"
        else:
            value = STALE_VALUES.get(task.id, "unknown")
            text = f"旧资料显示，{topic} 为 {value}。"
        return AgentAnswer(
            text=text,
            citations=list(task.gold_sources[:1]),
            tokens=800 if self.good else 600,
            latency_s=0.05,
            cost_usd=0.0,
        )


def _compose(
    task: BenchmarkTask,
    results: list[SearchResult],
    started: float,
    credits: float,
) -> AgentAnswer:
    lines = [f"问题：{task.question}"]
    for item in results[:5]:
        snippet = " ".join(item.content.split())[:220]
        lines.append(f"- {item.title}：{snippet}")
    text = "\n".join(lines)
    return AgentAnswer(
        text=text,
        citations=[item.url for item in results[:5]],
        tokens=0,
        latency_s=round(time.monotonic() - started, 2),
        cost_usd=round(credits * 0.008, 4),
    )


class RetrievalAdapter:
    """单轮检索基线：一次 search，直接拼接摘要（无规划、无核验）。"""

    def __init__(self, tavily: TavilyClient, *, max_results: int = 5) -> None:
        self.tavily = tavily
        self.max_results = max_results
        self.id = "retrieval_baseline"
        self.name = "Retrieval Baseline"
        self.description = "single search + snippet stitching"

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        results, credits = await self.tavily.search(task.question, max_results=self.max_results)
        return _compose(task, results, started, credits)


class ScoutAdapter:
    """YAI Scout 风格：先规划查询，再多查询检索后拼接（无 LLM）。"""

    def __init__(self, tavily: TavilyClient) -> None:
        self.tavily = tavily
        self.id = "scout"
        self.name = "YAI Scout (extractive)"
        self.description = "plan 2 queries + multi-query retrieval"

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        plan = build_plan(task.question, task.as_of)
        queries: list[str] = []
        for sub in plan.sub_questions:
            for query in sub.queries:
                if query not in queries:
                    queries.append(query)
        credits = 0.0
        merged: list[SearchResult] = []
        seen: set[str] = set()
        for query in queries[:2]:
            results, used = await self.tavily.search(query, max_results=3)
            credits += used
            for item in results:
                if item.url in seen:
                    continue
                seen.add(item.url)
                merged.append(item)
        return _compose(task, merged, started, credits)


LLM_SYSTEM = (
    "You are a careful research assistant. Answer the question using ONLY the provided sources. "
    "Cite sources with [n]. Keep the answer short and factual. "
    "If the sources do not contain the answer, say you cannot verify it."
)
LLM_USER = """Question: {question}
As of: {as_of}

Sources:
{sources}

Answer:"""


class LLMAgentAdapter:
    """单轮 RAG + LLM 回答：Tavily 检索 → 拼接来源 → DeepSeek 生成答案。"""

    def __init__(self, tavily: TavilyClient, llm: LLMClient, *, max_results: int = 4) -> None:
        self.tavily = tavily
        self.llm = llm
        self.max_results = max_results
        self.id = "llm_agent"
        self.name = "LLM Single-shot (RAG)"
        self.description = "Tavily retrieval + DeepSeek answer with citations"

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        results, credits = await self.tavily.search(task.question, max_results=self.max_results)
        sources = "\n".join(
            f"[{i + 1}] {item.title} ({item.published_date or 'date unknown'}): "
            f"{item.content[:300]}"
            for i, item in enumerate(results[: self.max_results])
        )
        result = await self.llm.chat_text(
            LLM_SYSTEM,
            LLM_USER.format(question=task.question, as_of=task.as_of, sources=sources),
            max_tokens=350,
        )
        if result is None:
            return AgentAnswer(
                text="",
                citations=[item.url for item in results],
                latency_s=round(time.monotonic() - started, 2),
                cost_usd=round(credits * 0.008, 4),
                error="LLM unavailable",
            )
        return AgentAnswer(
            text=result.text,
            citations=[item.url for item in results],
            tokens=result.prompt_tokens + result.completion_tokens,
            latency_s=round(time.monotonic() - started, 2),
            cost_usd=round(result.cost_usd + credits * 0.008, 6),
        )


class HttpAdapter:
    """外部 Agent：POST {question, as_of} → {answer, citations, tokens}。"""

    def __init__(self, spec_id: str, name: str, endpoint: str, *, timeout_s: float = 90.0) -> None:
        self.id = spec_id
        self.name = name
        self.description = f"http adapter → {endpoint}"
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(
                self.endpoint, json={"question": task.question, "as_of": task.as_of}
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        return AgentAnswer(
            text=str(data.get("answer") or ""),
            citations=[str(c) for c in (data.get("citations") or [])],
            tokens=int(data.get("tokens") or 0),
            latency_s=round(time.monotonic() - started, 2),
            cost_usd=float(data.get("cost_usd") or 0.0),
        )

