"""Research Director：确定性状态机的 G0 版本（Plan → Retrieve → 报告桩）。

每个阶段：发事件 → 落库 → 检查预算/墙钟。LLM 阶段（抽取/验证/合成）留接口，当前显式 skip。
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from ..config import Settings
from ..domain.models import (
    CostEntry,
    ResearchTask,
    RunEvent,
    Stage,
    TaskStatus,
    utcnow_iso,
)
from ..retrieval.tavily import TavilyClient, TavilyError
from ..store import Store
from .planning import build_plan, plan_queries
from .report import render_report
from .sourcing import to_source_record

TERMINAL_EVENTS = frozenset({"run_finished", "run_failed", "run_cancelled"})


class ResearchDirector:
    def __init__(self, store: Store, tavily: TavilyClient, settings: Settings) -> None:
        self.store = store
        self.tavily = tavily
        self.settings = settings
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------ public
    def start(self, task: ResearchTask) -> None:
        existing = self._tasks.get(task.id)
        if existing is not None and not existing.done():
            return
        job = asyncio.create_task(self._run(task), name=f"research:{task.id}")
        self._tasks[task.id] = job
        job.add_done_callback(lambda _job: self._tasks.pop(task.id, None))

    def active_count(self) -> int:
        return sum(1 for job in self._tasks.values() if not job.done())

    async def cancel(self, task_id: str) -> bool:
        job = self._tasks.get(task_id)
        if job is not None and not job.done():
            job.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await job
            # 任务可能在开始执行前就被取消（_run 未跑到状态更新），这里兜底。
            task = self.store.get_task(task_id)
            if task is not None and task.status not in {
                TaskStatus.DELIVERED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                self.store.update_task(
                    task_id,
                    status=TaskStatus.CANCELLED,
                    finished_at=utcnow_iso(),
                    stats={"cancelled": True},
                )
                self._emit(task_id, Stage.DONE, "run_cancelled", {"reason": "cancelled_by_user"})
            return True
        task = self.store.get_task(task_id)
        if task is not None and task.status is TaskStatus.RUNNING:
            self.store.update_task(
                task_id, status=TaskStatus.CANCELLED, finished_at=utcnow_iso()
            )
            self._emit(task_id, Stage.DONE, "run_cancelled", {"reason": "cancelled_by_user"})
            return True
        return False

    async def shutdown(self) -> None:
        jobs = [job for job in self._tasks.values() if not job.done()]
        for job in jobs:
            job.cancel()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)

    # ------------------------------------------------------------------ helpers
    def _emit(
        self, task_id: str, stage: Stage, event_type: str, payload: dict[str, Any] | None = None
    ) -> RunEvent:
        return self.store.append_event(
            RunEvent(task_id=task_id, stage=stage, type=event_type, payload=payload or {})
        )

    # ------------------------------------------------------------------ pipeline
    async def _run(self, task: ResearchTask) -> None:
        task_id = task.id
        started = time.monotonic()
        try:
            self.store.update_task(task_id, status=TaskStatus.RUNNING)

            # 1) 计划
            self._emit(
                task_id,
                Stage.PLANNING,
                "stage_started",
                {"stage": "planning", "label": "拆解研究问题"},
            )
            plan = build_plan(task.question, task.as_of)
            self.store.save_plan(task_id, plan)
            self._emit(
                task_id,
                Stage.PLANNING,
                "plan_ready",
                {
                    "sub_questions": [sq.model_dump() for sq in plan.sub_questions],
                    "stop_criteria": plan.stop_criteria,
                    "generated_by": plan.generated_by,
                },
            )
            self._emit(task_id, Stage.PLANNING, "stage_finished", {"stage": "planning"})

            # 2) 检索（并发 + 预算/墙钟守护）
            queries = plan_queries(plan)[: self.settings.max_queries]
            self._emit(
                task_id,
                Stage.RETRIEVING,
                "stage_started",
                {
                    "stage": "retrieving",
                    "queries": queries,
                    "max_credits": self.settings.max_tavily_credits,
                    "mode": self.tavily.mode,
                },
            )
            semaphore = asyncio.Semaphore(self.settings.max_concurrency)
            lock = asyncio.Lock()
            spent = 0.0
            reserved = 0.0
            failed = 0
            budget_hit = False
            # Reserve conservatively before each call; basic search costs 1 credit,
            # advanced costs 2. This prevents concurrent queries from overrunning
            # the task budget between the check and the actual charge.
            per_query_reserve = 2.0 if self.settings.search_depth == "advanced" else 1.0

            async def run_query(query: str) -> None:
                nonlocal spent, reserved, failed, budget_hit
                if time.monotonic() - started > self.settings.max_wall_clock_seconds:
                    budget_hit = True
                    return
                async with lock:
                    if spent + reserved + per_query_reserve > self.settings.max_tavily_credits:
                        budget_hit = True
                        return
                    reserved += per_query_reserve
                async with semaphore:
                    remaining = self.settings.max_wall_clock_seconds - (
                        time.monotonic() - started
                    )
                    try:
                        if remaining <= 0:
                            raise TimeoutError
                        results, credits = await asyncio.wait_for(
                            self.tavily.search(query), timeout=remaining
                        )
                    except (TavilyError, TimeoutError) as exc:
                        async with lock:
                            reserved -= per_query_reserve
                            failed += 1
                        self._emit(
                            task_id,
                            Stage.RETRIEVING,
                            "query_failed",
                            {"query": query, "error": str(exc)[:300]},
                        )
                        return
                    async with lock:
                        reserved -= per_query_reserve
                        spent += credits
                    self.store.add_cost(
                        CostEntry(
                            task_id=task_id,
                            provider="tavily",
                            unit="search",
                            amount=1.0,
                            credits=credits,
                            usd_estimate=round(credits * 0.008, 4),
                        )
                    )
                    added = 0
                    for result in results:
                        source = to_source_record(task_id, result)
                        if self.store.add_source(source):
                            added += 1
                            self._emit(
                                task_id,
                                Stage.RETRIEVING,
                                "source_found",
                                {
                                    "id": source.id,
                                    "title": source.title,
                                    "url": source.url,
                                    "domain": source.domain,
                                    "tier": source.tier,
                                    "published_at": source.published_at,
                                },
                            )
                    self._emit(
                        task_id,
                        Stage.RETRIEVING,
                        "cost_update",
                        {
                            "query": query,
                            "credits": credits,
                            "spent_credits": round(spent, 2),
                            "added_sources": added,
                        },
                    )

            await asyncio.gather(*(run_query(q) for q in queries))

            sources = self.store.list_sources(task_id)
            if budget_hit:
                self._emit(
                    task_id,
                    Stage.RETRIEVING,
                    "budget_exceeded",
                    {
                        "spent_credits": round(spent, 2),
                        "max_credits": self.settings.max_tavily_credits,
                    },
                )
            self._emit(task_id, Stage.RETRIEVING, "stage_finished", {"stage": "retrieving"})

            if not sources:
                raise RuntimeError("所有检索均失败：没有拿到任何来源（检查 Tavily key/网络/额度）")

            # 3) 抽取 / 验证（G0 显式跳过，不假装做过）
            for stage, label in ((Stage.EXTRACTING, "抽取证据"), (Stage.VERIFYING, "跨来源验证")):
                self._emit(task_id, stage, "stage_started", {"stage": stage.value, "label": label})
                self._emit(
                    task_id,
                    stage,
                    "stage_skipped",
                    {"stage": stage.value, "reason": "G0 骨架未实现（Charter M4/M5）"},
                )
                self._emit(task_id, stage, "stage_finished", {"stage": stage.value})

            # 4) 报告（桩）
            self._emit(
                task_id,
                Stage.REPORTING,
                "stage_started",
                {"stage": "reporting", "label": "生成报告"},
            )
            elapsed = time.monotonic() - started
            report_md = render_report(
                task,
                plan,
                sources,
                credits=spent,
                elapsed_s=elapsed,
                failed_queries=failed,
            )
            stats = {
                "sources": len(sources),
                "domains": len({s.domain for s in sources if s.domain}),
                "queries": len(queries),
                "failed_queries": failed,
                "credits": round(spent, 2),
                "elapsed_s": round(elapsed, 1),
                "mode": self.tavily.mode,
            }
            self.store.update_task(
                task_id,
                status=TaskStatus.DELIVERED,
                finished_at=utcnow_iso(),
                report_md=report_md,
                stats=stats,
            )
            self._emit(
                task_id,
                Stage.REPORTING,
                "report_ready",
                {"sources": len(sources), "report_chars": len(report_md)},
            )
            self._emit(task_id, Stage.REPORTING, "stage_finished", {"stage": "reporting"})
            self._emit(task_id, Stage.DONE, "run_finished", {"status": "delivered", **stats})

        except asyncio.CancelledError:
            self.store.update_task(
                task_id,
                status=TaskStatus.CANCELLED,
                finished_at=utcnow_iso(),
                stats={"cancelled": True},
            )
            self._emit(task_id, Stage.DONE, "run_cancelled", {"reason": "cancelled"})
        except Exception as exc:  # noqa: BLE001 - 顶层兜底必须把失败落库并可见
            message = f"{type(exc).__name__}: {exc}"[:500]
            self.store.update_task(
                task_id,
                status=TaskStatus.FAILED,
                finished_at=utcnow_iso(),
                error=message,
                stats={"failed": True},
            )
            self._emit(task_id, Stage.DONE, "run_failed", {"error": message})


