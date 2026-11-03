"""Benchmark JSON routes (supporting evaluation, not the primary submission)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from ..benchmark.dataset import load_dataset
from ..benchmark.manifest import result_hash as compute_result_hash
from ..benchmark.runner import DEFAULT_AGENT_SPECS, BenchmarkRunner
from ..benchmark.scoring import leaderboard as build_leaderboard
from ..benchmark.scoring import pareto_frontier
from ..config import Settings
from ..store import Store


class BenchmarkRequest(BaseModel):
    agent_ids: list[str] | None = None
    task_ids: list[str] | None = None


def register_benchmark_routes(
    app: FastAPI,
    *,
    cfg: Settings,
    store: Store,
    runner: BenchmarkRunner,
    guard_cost: Callable[[Request, str], None],
    can_access: Callable[[str, Request], bool],
    session_id: Callable[[Request, Response | None], str],
    is_admin: Callable[[Request], bool],
) -> None:
    @app.get("/api/benchmark/tasks")
    @app.get("/benchmark/tasks")
    async def benchmark_tasks() -> dict[str, Any]:
        version, tasks = load_dataset()
        public = [task for task in tasks if not task.hidden]
        return {
            "dataset_version": version,
            "tasks": [task.model_dump(mode="json") for task in public],
            "hidden_count": sum(1 for task in tasks if task.hidden),
            "hidden_status": "compromised",
        }

    @app.get("/api/benchmark/agents")
    @app.get("/benchmark/agents")
    async def benchmark_agents() -> dict[str, Any]:
        specs = [spec.model_dump(mode="json") for spec in DEFAULT_AGENT_SPECS]
        if cfg.http_agent_url:
            specs.append(
                {
                    "id": "external_http",
                    "name": "External HTTP Agent",
                    "kind": "http",
                    "description": f"scout-adapter/1.0 → {cfg.http_agent_url}",
                    "config": {"endpoint": cfg.http_agent_url},
                }
            )
        return {"agents": specs}

    @app.post("/api/benchmark/run", status_code=202)
    @app.post("/benchmark/runs", status_code=202)
    async def benchmark_run(
        payload: BenchmarkRequest, request: Request, response: Response
    ) -> dict[str, Any]:
        guard_cost(request, "benchmark")
        if cfg.benchmark_run_requires_admin and not is_admin(request):
            raise HTTPException(
                status_code=403,
                detail="benchmark run requires admin token",
            )
        try:
            session = runner.start(
                payload.agent_ids,
                payload.task_ids,
                owner_id=session_id(request, response),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"session": session.model_dump(mode="json")}

    @app.get("/api/benchmark/sessions/{session_id}")
    @app.get("/benchmark/runs/{session_id}")
    async def benchmark_session(session_id: str, request: Request) -> dict[str, Any]:
        session = await asyncio.to_thread(
            store.get_bench_session, session_id
        )
        if session is None or not can_access(session.owner_id, request):
            raise HTTPException(status_code=404, detail="session not found")
        results = await asyncio.to_thread(
            store.list_bench_results, session_id
        )
        return {
            "session": session.model_dump(mode="json"),
            "results": [result.model_dump(mode="json") for result in results],
            "leaderboard": build_leaderboard(results),
            "pareto": pareto_frontier(results),
        }

    @app.get("/benchmark/runs/{session_id}/verify")
    @app.get("/api/benchmark/runs/{session_id}/verify")
    async def verify_benchmark_run(session_id: str, request: Request) -> dict[str, Any]:
        session = await asyncio.to_thread(
            store.get_bench_session, session_id
        )
        if session is None or not can_access(session.owner_id, request):
            raise HTTPException(status_code=404, detail="session not found")
        results = await asyncio.to_thread(
            store.list_bench_results, session_id
        )
        computed = compute_result_hash(results)
        return {
            "session_id": session_id,
            "stored_result_hash": session.result_hash,
            "computed_result_hash": computed,
            "matches": session.result_hash == computed,
        }

    @app.get("/api/benchmark/leaderboard")
    @app.get("/benchmark/leaderboard")
    async def benchmark_leaderboard(
        session_id: str, request: Request
    ) -> dict[str, Any]:
        session = await asyncio.to_thread(
            store.get_bench_session, session_id
        )
        if session is None or not can_access(session.owner_id, request):
            raise HTTPException(status_code=404, detail="session not found")
        results = await asyncio.to_thread(
            store.list_bench_results, session_id
        )
        return {
            "session_id": session_id,
            "status": session.status,
            "leaderboard": build_leaderboard(results),
            "pareto": pareto_frontier(results),
        }
