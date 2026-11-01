"""Agent 适配器：统一「问题 → 答案 + 引用 + 成本」协议。"""

from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
import time
import uuid
from typing import Any, Protocol

import httpx

from ..domain.models import AgentAnswer, BenchmarkTask
from ..llm import LLMClient
from ..pipeline.planning import build_plan
from ..retrieval.tavily import SearchResult, TavilyClient
from .protocol import (
    AdapterExecution,
    AdapterManifest,
    AdapterRunRequest,
    AdapterTask,
    validate_run_response,
)

# demo 用的"过期知识"：用于展示 detector 与排行榜的差异
STALE_VALUES: dict[str, str] = {
    "b_tavily_free_credits": "500",
    "b_tavily_advanced_cost": "1",
    "b_tavily_student_plan": "2000",
    "b_deepseek_flash_price": "0.15",
    "b_bifrost_license": "AGPL-3.0",
    "c_yai_version": "0.24.0",
    "c_yai_license": "AGPL-3.0",
    "d_geekroom_deadline": "2026-11-22",
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


class PythonAdapter:
    """进程内 Agent：module:function 接收请求 dict，返回响应 dict（协议同 HTTP）。"""

    def __init__(self, spec_id: str, name: str, target: str) -> None:
        self.id = spec_id
        self.name = name
        self.target = target
        self.description = f"python adapter → {target}"

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        request = AdapterRunRequest(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            task=AdapterTask(
                task_id=task.id,
                question=task.question,
                target_time=task.as_of,
                category=task.category.value,
            ),
            execution=AdapterExecution(deadline_s=120),
        )
        try:
            module_name, _, func_name = self.target.partition(":")
            if not func_name:
                module_name, _, func_name = self.target.rpartition(".")
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name)
            payload = request.model_dump(mode="json")
            if inspect.iscoroutinefunction(func):
                result = await func(payload)
            else:
                result = await asyncio.to_thread(func, payload)
            response = validate_run_response(result)
        except Exception as exc:  # noqa: BLE001
            return AgentAnswer(
                text="",
                latency_s=round(time.monotonic() - started, 2),
                error=f"{type(exc).__name__}: {exc}",
            )
        return _response_to_answer(response, started)


class CLIAdapter:
    """子进程 Agent：stdin 收请求 JSON，stdout 返回响应 JSON。"""

    def __init__(
        self, spec_id: str, name: str, command: list[str], *, timeout_s: float = 120.0
    ) -> None:
        self.id = spec_id
        self.name = name
        self.command = command
        self.timeout_s = timeout_s
        self.description = f"cli adapter → {' '.join(command[:2])}"

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        request = AdapterRunRequest(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            task=AdapterTask(
                task_id=task.id,
                question=task.question,
                target_time=task.as_of,
                category=task.category.value,
            ),
            execution=AdapterExecution(deadline_s=int(self.timeout_s)),
        )
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                self.command,
                input=request.model_dump_json(),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"exit {result.returncode}: {result.stderr[:200]}")
            response = validate_run_response(json.loads(result.stdout))
        except Exception as exc:  # noqa: BLE001
            return AgentAnswer(
                text="",
                latency_s=round(time.monotonic() - started, 2),
                error=f"{type(exc).__name__}: {exc}",
            )
        return _response_to_answer(response, started)


def _response_to_answer(response: Any, started: float) -> AgentAnswer:
    return AgentAnswer(
        text=response.answer,
        citations=list(response.citations),
        tokens=response.usage.prompt_tokens + response.usage.completion_tokens,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        model=response.usage.model,
        provider=response.usage.provider,
        price_table_version=response.cost.price_table_version,
        estimated=response.cost.estimated,
        latency_s=round(response.latency_ms / 1000 or time.monotonic() - started, 2),
        cost_usd=float(response.cost.estimated_usd or 0.0),
        trace=list(response.trace),
        error=response.error,
    )


class HttpAdapter:
    """外部 Agent：实现 scout-adapter/1.0（GET /manifest + POST /run）。"""

    def __init__(
        self,
        spec_id: str,
        name: str,
        endpoint: str,
        *,
        timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.id = spec_id
        self.name = name
        self.description = f"http adapter → {endpoint}"
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s
        self.transport = transport

    async def manifest(self) -> AdapterManifest:
        async with httpx.AsyncClient(
            timeout=self.timeout_s, transport=self.transport
        ) as client:
            resp = await client.get(f"{self.endpoint}/manifest")
            resp.raise_for_status()
            return AdapterManifest.model_validate(resp.json())

    async def answer(self, task: BenchmarkTask) -> AgentAnswer:
        started = time.monotonic()
        request = AdapterRunRequest(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            task=AdapterTask(
                task_id=task.id,
                question=task.question,
                target_time=task.as_of,
                category=task.category.value,
            ),
            execution=AdapterExecution(
                deadline_s=int(self.timeout_s),
                tools_allowed=["web_search", "read_url"],
            ),
        )
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s, transport=self.transport
            ) as client:
                resp = await client.post(
                    f"{self.endpoint}/run", json=request.model_dump(mode="json")
                )
                resp.raise_for_status()
                response = validate_run_response(resp.json())
        except Exception as exc:  # noqa: BLE001 - 协议/网络错误统一转成失败结果
            return AgentAnswer(
                text="",
                latency_s=round(time.monotonic() - started, 2),
                error=f"{type(exc).__name__}: {exc}",
            )
        return AgentAnswer(
            text=response.answer,
            citations=list(response.citations),
            tokens=response.usage.prompt_tokens + response.usage.completion_tokens,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            model=response.usage.model,
            provider=response.usage.provider,
            price_table_version=response.cost.price_table_version,
            estimated=response.cost.estimated,
            latency_s=round(response.latency_ms / 1000 or time.monotonic() - started, 2),
            cost_usd=float(response.cost.estimated_usd or 0.0),
            trace=list(response.trace),
            error=response.error,
        )

