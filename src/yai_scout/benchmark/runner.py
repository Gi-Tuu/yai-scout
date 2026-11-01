"""Benchmark 运行器：任务 × Agent → 评分 → 落库。"""

from __future__ import annotations

import asyncio
import time
import uuid

from ..detector.service import StaleAnswerDetector
from ..domain.models import (
    AgentAnswer,
    AgentSpec,
    BenchmarkTask,
    BenchSession,
    TaskResult,
    utcnow_iso,
)
from ..store import Store
from .adapters import AgentAdapter
from .dataset import load_tasks
from .scoring import composite_score, numeric_accuracy

DEFAULT_AGENT_SPECS: list[AgentSpec] = [
    AgentSpec(
        id="mock_good", name="Mock (fresh)", kind="mock", description="synthetic correct answers"
    ),
    AgentSpec(
        id="mock_stale", name="Mock (stale)", kind="mock", description="synthetic outdated answers"
    ),
    AgentSpec(
        id="retrieval_baseline",
        name="Retrieval Baseline",
        kind="retrieval_baseline",
        description="single search + snippet stitching",
    ),
    AgentSpec(
        id="llm_agent",
        name="LLM Single-shot (RAG)",
        kind="llm",
        description="Tavily retrieval + DeepSeek answer with citations",
    ),
]


class BenchmarkRunner:
    def __init__(
        self,
        store: Store,
        adapters: dict[str, AgentAdapter],
        detector: StaleAnswerDetector | None,
        *,
        concurrency: int = 2,
        detect_freshness: bool = True,
        max_claims: int = 2,
        timeout_s: float = 120.0,
    ) -> None:
        self.store = store
        self.adapters = adapters
        self.detector = detector
        self.concurrency = concurrency
        self.detect_freshness = detect_freshness
        self.max_claims = max_claims
        self.timeout_s = timeout_s
        self._sessions: dict[str, asyncio.Task[None]] = {}

    def start(
        self, agent_ids: list[str] | None = None, task_ids: list[str] | None = None
    ) -> BenchSession:
        chosen_agents = [agent_id for agent_id in (agent_ids or []) if agent_id in self.adapters]
        if agent_ids and not chosen_agents:
            raise ValueError(f"unknown agent ids: {agent_ids}")
        if not chosen_agents:
            chosen_agents = [spec.id for spec in DEFAULT_AGENT_SPECS if spec.id in self.adapters]
        all_tasks = {task.id: task for task in load_tasks()}
        chosen_tasks = task_ids or list(all_tasks)
        missing = [task_id for task_id in chosen_tasks if task_id not in all_tasks]
        if missing:
            raise ValueError(f"unknown task ids: {missing}")
        session = BenchSession(
            id=f"bench_{uuid.uuid4().hex[:10]}",
            status="running",
            agent_ids=chosen_agents,
            task_ids=chosen_tasks,
        )
        self.store.create_bench_session(session)
        job = asyncio.create_task(
            self._run(session, chosen_agents, [all_tasks[t] for t in chosen_tasks]),
            name=f"benchmark:{session.id}",
        )
        self._sessions[session.id] = job
        job.add_done_callback(lambda _job: self._sessions.pop(session.id, None))
        return session

    async def _run(
        self, session: BenchSession, agent_ids: list[str], tasks: list[BenchmarkTask]
    ) -> None:
        started = time.monotonic()
        semaphore = asyncio.Semaphore(self.concurrency)
        try:
            async def run_one(task: BenchmarkTask, agent_id: str) -> TaskResult:
                adapter = self.adapters[agent_id]
                async with semaphore:
                    try:
                        answer = await asyncio.wait_for(
                            adapter.answer(task), timeout=self.timeout_s
                        )
                    except Exception as exc:  # noqa: BLE001 - 单个 Agent 失败不应中断整场评测
                        answer = AgentAnswer(text="", error=f"{type(exc).__name__}: {exc}")

                    freshness: int | None = None
                    stale_rate: float | None = None
                    if self.detector is not None and self.detect_freshness and answer.text:
                        try:
                            report = await self.detector.detect(
                                answer.text, max_claims=self.max_claims
                            )
                            freshness = report.overall_score
                            stale_rate = (
                                report.stale_claims / len(report.claims) if report.claims else 0.0
                            )
                        except Exception:  # noqa: BLE001 - freshness 失败不影响主分
                            freshness = None

                    numeric = numeric_accuracy(task.gold_values, answer.text)
                    result = TaskResult(
                        task_id=task.id,
                        agent_id=agent_id,
                        answer=answer,
                        numeric_accuracy=numeric,
                        has_citations=bool(answer.citations),
                        citation_count=len(answer.citations),
                        freshness_score=freshness,
                        stale_claim_rate=stale_rate,
                        score=composite_score(
                            numeric=numeric,
                            has_citations=bool(answer.citations),
                            stale_rate=stale_rate,
                            completed=bool(answer.text),
                            cost_usd=answer.cost_usd,
                        ),
                        error=answer.error,
                    )
                    self.store.add_bench_result(session.id, result)
                    return result

            await asyncio.gather(
                *(run_one(task, agent_id) for task in tasks for agent_id in agent_ids)
            )
            self.store.update_bench_session(
                session.id, status="done", finished_at=utcnow_iso()
            )
        except Exception as exc:  # noqa: BLE001 - 顶层兜底
            self.store.update_bench_session(
                session.id,
                status="failed",
                finished_at=utcnow_iso(),
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            _ = time.monotonic() - started

    async def shutdown(self) -> None:
        jobs = [job for job in self._sessions.values() if not job.done()]
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)

