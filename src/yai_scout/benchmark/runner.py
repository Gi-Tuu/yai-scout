"""Benchmark 运行器：任务 × Agent → 评分 → 落库。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid

from ..detector.service import StaleAnswerDetector
from ..domain.models import (
    AgentAnswer,
    AgentSpec,
    BenchmarkTask,
    BenchSession,
    TaskResult,
    TemporalSensitivity,
    utcnow_iso,
)
from ..store import Store
from .adapters import AgentAdapter
from .dataset import load_dataset
from .scoring import claim_coverage, evidence_metrics, expected_accuracy, weighted_view

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
            chosen_agents = [
                spec.id
                for spec in DEFAULT_AGENT_SPECS
                if spec.id in self.adapters and spec.kind != "http"
            ]
        dataset_version, all_task_list = load_dataset()
        all_tasks = {task.id: task for task in all_task_list}
        public_tasks = [task.id for task in all_task_list if not task.hidden]
        chosen_tasks = task_ids or public_tasks
        missing = [task_id for task_id in chosen_tasks if task_id not in all_tasks]
        if missing:
            raise ValueError(f"unknown task ids: {missing}")
        config_hash = hashlib.sha256(
            json.dumps(
                {
                    "agents": chosen_agents,
                    "tasks": chosen_tasks,
                    "dataset": dataset_version,
                    "target_time": [
                        all_tasks[t].as_of for t in chosen_tasks
                    ],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]
        session = BenchSession(
            id=f"bench_{uuid.uuid4().hex[:10]}",
            status="running",
            agent_ids=chosen_agents,
            task_ids=chosen_tasks,
            dataset_version=dataset_version,
            config_hash=config_hash,
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

                    freshness: float | None = None
                    stale_rate: float | None = None
                    metrics: dict[str, float | None] = {}
                    report = None
                    if self.detector is not None and self.detect_freshness and answer.text:
                        try:
                            report = await self.detector.detect(
                                answer.text, as_of=task.as_of, max_claims=self.max_claims
                            )
                            freshness = report.overall_score
                            temporal = [
                                c
                                for c in report.claims
                                if c.temporal_sensitivity
                                in {TemporalSensitivity.SENSITIVE, TemporalSensitivity.VOLATILE}
                            ]
                            if temporal:
                                stale_rate = round(
                                    sum(
                                        1
                                        for v in report.verdicts
                                        if v.claim_id
                                        in {c.id for c in temporal}
                                        and v.status.value == "stale"
                                    )
                                    / len(temporal),
                                    3,
                                )
                            metrics = evidence_metrics(report)
                        except Exception:  # noqa: BLE001 - freshness 失败不影响主分
                            freshness = None

                    numeric = expected_accuracy(task, answer.text)
                    coverage = claim_coverage(task, answer.text)
                    stable_integrity = (
                        metrics.get("stable_fact_integrity")
                        if task.category.value == "stable"
                        else None
                    )
                    result = TaskResult(
                        task_id=task.id,
                        agent_id=agent_id,
                        answer=answer,
                        numeric_accuracy=numeric,
                        has_citations=bool(answer.citations),
                        citation_count=len(answer.citations),
                        freshness_score=freshness,
                        stale_claim_rate=stale_rate,
                        claim_coverage=coverage,
                        supported_claim_rate=metrics.get("supported_claim_rate"),
                        stable_fact_integrity=stable_integrity,
                        evidence_quality=metrics.get("evidence_quality"),
                        score=weighted_view(
                            accuracy=numeric,
                            freshness=freshness,
                            stale_rate=stale_rate,
                            evidence_quality=metrics.get("evidence_quality"),
                            completion=1.0 if answer.text else 0.0,
                            cost_usd=answer.cost_usd,
                            latency_s=answer.latency_s,
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




