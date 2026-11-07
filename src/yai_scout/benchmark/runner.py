"""Benchmark 运行器：任务 × Agent → 评分 → 落库。"""

from __future__ import annotations

import asyncio
import contextlib
import random
import statistics
import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from ..config import Settings
from ..detector.service import StaleAnswerDetector
from ..detector.versions import POLICY_VERSION, WEIGHTS_VERSION
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
from .manifest import build_manifest
from .manifest import config_hash as compute_config_hash
from .manifest import result_hash as compute_result_hash
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


class FailureInjection(BaseModel):
    """Deterministic fault injection for benchmark reliability runs."""

    enabled: bool = False
    rate: float = Field(default=0.0, ge=0.0, le=1.0)
    modes: list[
        Literal[
            "error",
            "timeout",
            "empty",
            "tool_timeout",
            "tool_error",
            "model_unavailable",
            "misleading_instruction",
        ]
    ] = Field(default=["error"])


class BenchmarkRunner:
    def __init__(
        self,
        store: Store,
        adapters: dict[str, AgentAdapter],
        detector: StaleAnswerDetector | None,
        *,
        cfg: Settings | None = None,
        agent_specs: dict[str, AgentSpec] | None = None,
        concurrency: int = 2,
        detector_concurrency: int = 2,
        detect_freshness: bool = True,
        max_claims: int = 2,
        timeout_s: float = 120.0,
    ) -> None:
        self.store = store
        self.adapters = adapters
        self.detector = detector
        self.cfg = cfg or Settings()
        self.agent_specs = agent_specs or {
            spec.id: spec for spec in DEFAULT_AGENT_SPECS
        }
        # 自定义 adapter 也必须出现在 manifest 中；缺失 spec 时用安全的占位描述。
        for adapter_id, adapter in adapters.items():
            self.agent_specs.setdefault(
                adapter_id,
                AgentSpec(
                    id=adapter_id,
                    name=getattr(adapter, "name", adapter_id),
                    kind="http",
                    description=type(adapter).__name__,
                ),
            )
        self.concurrency = concurrency
        self.detector_concurrency = max(1, detector_concurrency)
        self.detect_freshness = detect_freshness
        self.max_claims = max_claims
        self.timeout_s = timeout_s
        self._sessions: dict[str, asyncio.Task[None]] = {}
        self._detector_gate: asyncio.Semaphore | None = None
        self._detector_gate_loop: asyncio.AbstractEventLoop | None = None

    def _detector_semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._detector_gate is None or self._detector_gate_loop is not loop:
            self._detector_gate = asyncio.Semaphore(self.detector_concurrency)
            self._detector_gate_loop = loop
        return self._detector_gate

    def start(
        self,
        agent_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
        *,
        allow_hidden: bool = False,
        supersedes: str | None = None,
        owner_id: str = "",
        repeats: int = 1,
        failure_injection: FailureInjection | None = None,
        detect_freshness: bool | None = None,
    ) -> BenchSession:
        if not 1 <= repeats <= 5:
            raise ValueError("repeats must be between 1 and 5")
        effective_freshness = (
            self.detect_freshness if detect_freshness is None else detect_freshness
        )
        requested_agents = list(dict.fromkeys(agent_ids or []))
        unknown_agents = [
            agent_id for agent_id in requested_agents if agent_id not in self.adapters
        ]
        if unknown_agents:
            raise ValueError(f"unknown agent ids: {unknown_agents}")
        chosen_agents = requested_agents
        if not chosen_agents:
            chosen_agents = [
                spec.id
                for spec in DEFAULT_AGENT_SPECS
                if spec.id in self.adapters and spec.kind != "http"
            ]
        dataset_version, all_task_list = load_dataset()
        all_tasks = {task.id: task for task in all_task_list}
        public_tasks = [task.id for task in all_task_list if not task.hidden]
        chosen_tasks = list(dict.fromkeys(task_ids or public_tasks))
        missing = [task_id for task_id in chosen_tasks if task_id not in all_tasks]
        if missing:
            raise ValueError(f"unknown task ids: {missing}")
        hidden = [task_id for task_id in chosen_tasks if all_tasks[task_id].hidden]
        if hidden and not allow_hidden:
            raise ValueError("hidden tasks require private execution context")
        chosen_task_models = [all_tasks[t] for t in chosen_tasks]
        session_id = f"bench_{uuid.uuid4().hex[:10]}"
        started_at = utcnow_iso()
        manifest = build_manifest(
            experiment_id=session_id,
            dataset_version=dataset_version,
            tasks=chosen_task_models,
            agents=[
                self.agent_specs[agent_id]
                for agent_id in chosen_agents
                if agent_id in self.agent_specs
            ],
            cfg=self.cfg,
            snapshot_ids=[s.id for s in self.store.list_snapshots(limit=1000)],
            started_at=started_at,
            policy_version=POLICY_VERSION,
            weights_version=WEIGHTS_VERSION,
            agent_timeout_s=self.timeout_s,
            max_claims=self.max_claims,
            detect_freshness=effective_freshness,
            repeats=repeats,
            failure_injection=(
                failure_injection.model_dump(mode="json")
                if failure_injection is not None
                else {}
            ),
        )
        manifest.config_hash = compute_config_hash(manifest)
        session = BenchSession(
            id=session_id,
            owner_id=owner_id,
            status="running",
            agent_ids=chosen_agents,
            task_ids=chosen_tasks,
            dataset_version=dataset_version,
            config_hash=manifest.config_hash,
            manifest=manifest,
            supersedes=supersedes,
            created_at=started_at,
        )
        self.store.create_bench_session(session)
        job = asyncio.create_task(
            self._run(
                session,
                chosen_agents,
                chosen_task_models,
                repeats,
                failure_injection,
                effective_freshness,
            ),
            name=f"benchmark:{session.id}",
        )
        self._sessions[session.id] = job
        job.add_done_callback(lambda _job: self._sessions.pop(session.id, None))
        return session

    async def _run(
        self,
        session: BenchSession,
        agent_ids: list[str],
        tasks: list[BenchmarkTask],
        repeats: int,
        failure_injection: FailureInjection | None,
        detect_freshness: bool,
    ) -> None:
        started = time.monotonic()
        semaphore = asyncio.Semaphore(self.concurrency)
        detector_gate = self._detector_semaphore()

        async def run_repeat(
            task: BenchmarkTask, agent_id: str, repeat: int
        ) -> tuple[TaskResult, str | None, list[dict[str, object]]]:
            adapter = self.adapters[agent_id]
            trace: list[dict[str, object]] = [
                {
                    "step": "run.started",
                    "task_id": task.id,
                    "agent_id": agent_id,
                    "repeat": repeat,
                }
            ]
            fault: str | None = None
            answer: AgentAnswer | None = None
            if (
                failure_injection is not None
                and failure_injection.enabled
                and failure_injection.modes
            ):
                rng = random.Random(
                    f"{task.id}:{agent_id}:{repeat}:"
                    f"{failure_injection.model_dump_json()}"
                )
                if rng.random() < failure_injection.rate:
                    fault = rng.choice(failure_injection.modes)
                    trace.append({"step": "fault.injected", "mode": fault})
                    answer = AgentAnswer(
                        text="",
                        error=(
                            None
                            if fault == "empty"
                            else f"InjectedFailure: {fault}"
                        ),
                    )
            if answer is None:
                async with semaphore:
                    try:
                        answer = await asyncio.wait_for(
                            adapter.answer(task), timeout=self.timeout_s
                        )
                        trace.append(
                            {
                                "step": "adapter.completed",
                                "status": "ok",
                                "latency_s": answer.latency_s,
                            }
                        )
                    except Exception as exc:  # noqa: BLE001 - one agent failure must not stop the run
                        answer = AgentAnswer(
                            text="", error=f"{type(exc).__name__}: {exc}"
                        )
                        trace.append(
                            {
                                "step": "adapter.completed",
                                "status": "error",
                                "error": type(exc).__name__,
                            }
                        )
                for event in answer.trace[:20]:
                    trace.append({"step": "adapter.trace", "event": event})

            freshness: float | None = None
            stale_rate: float | None = None
            metrics: dict[str, float | None] = {}
            if self.detector is not None and detect_freshness and answer.text:
                async with detector_gate:
                    try:
                        report = await self.detector.detect(
                            answer.text, as_of=task.as_of, max_claims=self.max_claims
                        )
                        freshness = report.overall_score
                        temporal = [
                            c
                            for c in report.claims
                            if c.temporal_sensitivity
                            in {
                                TemporalSensitivity.SENSITIVE,
                                TemporalSensitivity.VOLATILE,
                            }
                        ]
                        if temporal:
                            stale_rate = round(
                                sum(
                                    1
                                    for v in report.verdicts
                                    if v.claim_id in {c.id for c in temporal}
                                    and v.status.value == "stale"
                                )
                                / len(temporal),
                                3,
                            )
                        metrics = evidence_metrics(report)
                        trace.append({"step": "freshness.completed", "status": "ok"})
                    except Exception:  # noqa: BLE001 - freshness failure must not stop the run
                        freshness = None
                        trace.append({"step": "freshness.completed", "status": "error"})

            numeric = expected_accuracy(task, answer.text)
            coverage = claim_coverage(task, answer.text)
            steps = len(answer.trace)
            tool_calls = sum(
                1
                for event in answer.trace
                if str(event.get("step", "")).startswith("tool.")
                or bool(event.get("tool"))
            )
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
                steps=steps,
                tool_calls=tool_calls,
            )
            trace.append({"step": "score.completed", "score": result.score})
            return result, fault, trace[:100]

        async def run_cell(task: BenchmarkTask, agent_id: str) -> None:
            samples: list[
                tuple[TaskResult, str | None, list[dict[str, object]]]
            ] = []
            for repeat in range(repeats):
                samples.append(await run_repeat(task, agent_id, repeat))
            all_samples = samples
            valid_samples = [
                item
                for item in all_samples
                if not item[0].error and item[0].answer.text.strip()
            ]
            scores_pool = valid_samples or all_samples
            base = max(scores_pool, key=lambda item: item[0].score)
            samples = scores_pool
            scores = [item[0].score for item in scores_pool]
            successes = len(valid_samples)
            faults = sorted({fault for _result, fault, _trace in all_samples if fault})
            trace: list[dict[str, object]] = []
            for _result, _fault, sample_trace in all_samples:
                trace.extend(sample_trace)
            trace = trace[:100]

            def average(values: list[float | None]) -> float | None:
                usable = [value for value in values if value is not None]
                return round(sum(usable) / len(usable), 4) if usable else None

            aggregate = base[0].model_copy(
                update={
                    "score": round(sum(scores) / len(scores), 4),
                    "numeric_accuracy": round(
                        sum(item[0].numeric_accuracy for item in samples) / repeats, 3
                    ),
                    "has_citations": any(item[0].has_citations for item in samples),
                    "citation_count": round(
                        sum(item[0].citation_count for item in samples) / repeats
                    ),
                    "freshness_score": average(
                        [item[0].freshness_score for item in samples]
                    ),
                    "stale_claim_rate": average(
                        [item[0].stale_claim_rate for item in samples]
                    ),
                    "claim_coverage": round(
                        sum(item[0].claim_coverage for item in samples) / repeats, 3
                    ),
                    "supported_claim_rate": average(
                        [item[0].supported_claim_rate for item in samples]
                    ),
                    "stable_fact_integrity": average(
                        [item[0].stable_fact_integrity for item in samples]
                    ),
                    "evidence_quality": average(
                        [item[0].evidence_quality for item in samples]
                    ),
                    "repeats": repeats,
                    "score_std": (
                        round(statistics.pstdev(scores), 4) if repeats > 1 else 0.0
                    ),
                    "success_rate": round(successes / repeats, 3),
                    "faults": faults,
                    "trace": trace,
                    "samples": [
                        {
                            "score": result.score,
                            "numeric_accuracy": result.numeric_accuracy,
                            "freshness_score": result.freshness_score,
                            "stale_claim_rate": result.stale_claim_rate,
                            "latency_s": result.answer.latency_s,
                            "cost_usd": result.answer.cost_usd,
                            "steps": result.steps,
                            "tool_calls": result.tool_calls,
                            "error": result.error,
                            "fault": fault,
                        }
                        for result, fault, _trace in all_samples
                    ],
                    "error": (
                        None
                        if successes == repeats
                        else (
                            base[0].error
                            if repeats == 1
                            else f"{repeats - successes}/{repeats} runs failed"
                        )
                    ),
                }
            )
            self.store.add_bench_result(session.id, aggregate)

        try:
            outcomes = await asyncio.gather(
                *(run_cell(task, agent_id) for task in tasks for agent_id in agent_ids),
                return_exceptions=True,
            )
            cancelled = [
                outcome for outcome in outcomes
                if isinstance(outcome, asyncio.CancelledError)
            ]
            if cancelled:
                raise cancelled[0]
            failures = [
                outcome for outcome in outcomes
                if isinstance(outcome, Exception)
            ]
            if failures:
                detail = "; ".join(
                    f"{type(exc).__name__}: {exc}" for exc in failures[:5]
                )
                raise RuntimeError(
                    f"{len(failures)} benchmark cells failed: {detail}"
                ) from failures[0]
            finished_at = utcnow_iso()
            results = self.store.list_bench_results(session.id)
            digest = compute_result_hash(results)
            final_manifest = None
            if session.manifest is not None:
                final_manifest = session.manifest.model_copy(
                    update={
                        "finished_at": finished_at,
                        "status": "done",
                        "result_hash": digest,
                    }
                )
            self.store.update_bench_session(
                session.id,
                status="done",
                finished_at=finished_at,
                result_hash=digest,
                manifest_json=(
                    final_manifest.model_dump_json() if final_manifest else None
                ),
            )
        except asyncio.CancelledError:
            # app shutdown cancels the background job; persist a terminal state
            # instead of leaving a permanently-running session row.
            finished_at = utcnow_iso()
            error = "benchmark run cancelled by shutdown"
            results = self.store.list_bench_results(session.id)
            digest = compute_result_hash(results)
            final_manifest = None
            if session.manifest is not None:
                final_manifest = session.manifest.model_copy(
                    update={
                        "finished_at": finished_at,
                        "status": "failed",
                        "result_hash": digest,
                    }
                )
            with contextlib.suppress(Exception):
                self.store.update_bench_session(
                    session.id,
                    status="failed",
                    finished_at=finished_at,
                    error=error,
                    result_hash=digest,
                    manifest_json=(
                        final_manifest.model_dump_json() if final_manifest else None
                    ),
                )
            raise
        except Exception as exc:  # noqa: BLE001 - top-level run failure
            finished_at = utcnow_iso()
            error = f"{type(exc).__name__}: {exc}"
            results = self.store.list_bench_results(session.id)
            digest = compute_result_hash(results)
            final_manifest = None
            if session.manifest is not None:
                final_manifest = session.manifest.model_copy(
                    update={
                        "finished_at": finished_at,
                        "status": "failed",
                        "result_hash": digest,
                    }
                )
            self.store.update_bench_session(
                session.id,
                status="failed",
                finished_at=finished_at,
                error=error,
                result_hash=digest,
                manifest_json=(
                    final_manifest.model_dump_json() if final_manifest else None
                ),
            )
        finally:
            _ = time.monotonic() - started

    async def shutdown(self) -> None:
        jobs = [job for job in self._sessions.values() if not job.done()]
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)







