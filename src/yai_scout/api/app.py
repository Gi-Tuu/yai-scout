"""FastAPI 应用：REST + SSE + 静态研究控制台。"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..benchmark.adapters import HttpAdapter
from ..benchmark.dataset import load_dataset
from ..benchmark.registry import DEFAULT_AGENT_SPECS, build_adapters
from ..benchmark.runner import BenchmarkRunner
from ..benchmark.scoring import leaderboard as build_leaderboard
from ..benchmark.scoring import pareto_frontier
from ..config import Settings, get_settings
from ..detector.service import StaleAnswerDetector
from ..domain.models import ResearchTask, RunEvent, TaskStatus
from ..llm import LLMClient
from ..pipeline.director import TERMINAL_EVENTS, ResearchDirector
from ..retrieval.tavily import TavilyClient
from ..store import Store


class CreateResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of: str | None = None


class DetectRequest(BaseModel):
    answer: str = Field(min_length=10, max_length=8000)
    as_of: str | None = None
    max_claims: int = Field(default=6, ge=1, le=12)


class BenchmarkRequest(BaseModel):
    agent_ids: list[str] | None = None
    task_ids: list[str] | None = None


def _sse(event: RunEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"id: {event.seq}\nevent: {event.type}\ndata: {data}\n\n"


def create_app(
    *,
    settings: Settings | None = None,
    tavily: TavilyClient | None = None,
    store: Store | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    static_dir = cfg.web_dir / "static"
    index_file = static_dir / "index.html"
    store = store or Store(cfg.db_path)
    tavily = tavily or TavilyClient(
        cfg.tavily_api_key,
        base_url=cfg.tavily_base_url,
        allow_keyless=cfg.tavily_allow_keyless,
        timeout=cfg.tavily_timeout_seconds,
        search_depth=cfg.search_depth,
        max_results=cfg.max_results_per_query,
    )
    director = ResearchDirector(store, tavily, cfg)
    llm = LLMClient(
        cfg.openai_api_key,
        base_url=cfg.openai_base_url,
        model=cfg.llm_model,
    )
    detector = StaleAnswerDetector(
        tavily,
        as_of=cfg.default_as_of,
        max_claims=6,
        concurrency=3,
        llm=llm,
    )
    adapters = build_adapters(tavily, llm)
    if cfg.http_agent_url:
        adapters["external_http"] = HttpAdapter(
            "external_http", "External HTTP Agent", cfg.http_agent_url
        )
    runner = BenchmarkRunner(store, adapters, detector)
    benchmark_enabled = cfg.scout_mode in {"all", "benchmark"}
    freshness_enabled = cfg.scout_mode in {"all", "freshness"}

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await director.shutdown()
        await runner.shutdown()
        await tavily.aclose()
        await llm.aclose()
        store.close()

    app = FastAPI(title=cfg.app_name, version=cfg.app_version, lifespan=lifespan)

    @app.middleware("http")
    async def mode_guard(request: Request, call_next: Any) -> Any:
        path = request.url.path
        if not benchmark_enabled and path.startswith(("/benchmark", "/api/benchmark")):
            return JSONResponse({"detail": "benchmark mode disabled"}, status_code=404)
        if not freshness_enabled and path.startswith(("/freshness", "/api/detector")):
            return JSONResponse({"detail": "freshness mode disabled"}, status_code=404)
        return await call_next(request)

    # ------------------------------------------------------------------ meta
    @app.get("/api/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "app": cfg.app_name,
            "version": cfg.app_version,
            "mode": cfg.scout_mode,
            "tavily": {"mode": tavily.mode, "authenticated": tavily.authenticated},
            "llm": {"available": llm.available, "model": cfg.llm_model},
        }

    # ------------------------------------------------------------------ research
    @app.post("/api/research", status_code=202)
    async def create_research(payload: CreateResearchRequest) -> dict[str, Any]:
        task = ResearchTask(
            id=f"task_{uuid.uuid4().hex[:12]}",
            question=" ".join(payload.question.split()),
            as_of=payload.as_of or cfg.default_as_of,
        )
        store.create_task(task)
        director.start(task)
        return {
            "task": task.model_dump(mode="json"),
            "events_url": f"/api/research/{task.id}/events",
        }

    @app.get("/api/research")
    async def list_research(limit: int = 20) -> dict[str, Any]:
        return {"tasks": [t.model_dump(mode="json") for t in store.list_tasks(limit=limit)]}

    @app.get("/api/research/{task_id}")
    async def get_research(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        plan = store.get_plan(task_id)
        credits, usd = store.cost_sum(task_id)
        return {
            "task": task.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json") if plan else None,
            "sources": [s.model_dump(mode="json") for s in store.list_sources(task_id)],
            "cost": {"credits": round(credits, 3), "usd": round(usd, 4)},
            "event_count": len(store.list_events(task_id, 0, 10000)),
        }

    @app.post("/api/research/{task_id}/cancel")
    async def cancel_research(task_id: str) -> dict[str, Any]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        cancelled = await director.cancel(task_id)
        return {"cancelled": cancelled}

    @app.get("/api/research/{task_id}/events")
    async def research_events(task_id: str, request: Request) -> StreamingResponse:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        cursor = 0
        header = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
        if header and header.isdigit():
            cursor = int(header)

        async def stream() -> AsyncIterator[str]:
            nonlocal cursor
            idle = 0.0
            while True:
                if await request.is_disconnected():
                    return
                events = store.list_events(task_id, cursor, 200)
                for event in events:
                    cursor = event.seq
                    yield _sse(event)
                    if event.type in TERMINAL_EVENTS:
                        return
                await asyncio.sleep(0.25)
                idle += 0.25
                if idle >= 15:
                    idle = 0.0
                    yield ": ping\n\n"
                    task = store.get_task(task_id)
                    if task is not None and task.status in {
                        TaskStatus.DELIVERED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    }:
                        yield (
                            "event: stream_closed\n"
                            f"data: {json.dumps({'status': task.status.value})}\n\n"
                        )
                        return

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ------------------------------------------------------------------ detector
    @app.post("/api/detector")
    @app.post("/freshness/verify")
    async def detect(payload: DetectRequest) -> dict[str, Any]:
        report = await detector.detect(
            payload.answer,
            as_of=payload.as_of,
            max_claims=payload.max_claims,
        )
        store.save_detector_report(report)
        return report.model_dump(mode="json")

    @app.get("/api/detector/{report_id}")
    @app.get("/freshness/reports/{report_id}")
    async def get_detector_report(report_id: str) -> dict[str, Any]:
        report = store.get_detector_report(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        return report.model_dump(mode="json")

    @app.get("/freshness/reports")
    async def list_detector_reports(limit: int = 20) -> dict[str, Any]:
        reports = store.list_detector_reports(limit=limit)
        return {
            "reports": [
                {
                    "id": report.id,
                    "as_of": report.as_of,
                    "overall_score": report.overall_score,
                    "stale_claims": report.stale_claims,
                    "claims": len(report.claims),
                    "created_at": report.created_at,
                }
                for report in reports
            ]
        }

    @app.get("/freshness/reports/{report_id}/export")
    async def export_detector_report(report_id: str) -> dict[str, Any]:
        report = store.get_detector_report(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        lines = [
            f"# Freshness Report {report.id}",
            "",
            f"- as_of: {report.as_of}",
            f"- overall: {report.overall_score}",
            f"- claims: {len(report.claims)} / stale: {report.stale_claims}",
            f"- policy: {report.policy_version} / weights: {report.weights_version}",
            "",
        ]
        verdicts = {v.claim_id: v for v in report.verdicts}
        for claim in report.claims:
            verdict = verdicts.get(claim.id)
            lines.append(f"## {claim.text}")
            lines.append(
                f"- type: {claim.type} / sensitivity: {claim.temporal_sensitivity}"
            )
            if verdict:
                lines.append(
                    f"- status: {verdict.status} / score: {verdict.score} "
                    f"/ confidence: {verdict.confidence}"
                )
                lines.append(f"- rationale: {verdict.rationale}")
                if verdict.suggestion:
                    lines.append(f"- suggestion: {verdict.suggestion}")
                for ev in verdict.evidence:
                    lines.append(
                        f"  - [{ev.relation}] {ev.title or ev.url} "
                        f"({ev.published_at or 'unknown'}, T{ev.tier})"
                    )
            lines.append("")
        return {"markdown": "\n".join(lines)}

    # ------------------------------------------------------------------ benchmark
    @app.get("/api/benchmark/tasks")
    @app.get("/benchmark/tasks")
    async def benchmark_tasks(include_hidden: bool = False) -> dict[str, Any]:
        version, tasks = load_dataset()
        visible = tasks if include_hidden else [task for task in tasks if not task.hidden]
        return {
            "dataset_version": version,
            "tasks": [task.model_dump(mode="json") for task in visible],
            "hidden_count": sum(1 for task in tasks if task.hidden),
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
    async def benchmark_run(payload: BenchmarkRequest) -> dict[str, Any]:
        try:
            session = runner.start(payload.agent_ids, payload.task_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"session": session.model_dump(mode="json")}

    @app.get("/api/benchmark/sessions/{session_id}")
    @app.get("/benchmark/runs/{session_id}")
    async def benchmark_session(session_id: str) -> dict[str, Any]:
        session = store.get_bench_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        results = store.list_bench_results(session_id)
        return {
            "session": session.model_dump(mode="json"),
            "results": [result.model_dump(mode="json") for result in results],
            "leaderboard": build_leaderboard(results),
            "pareto": pareto_frontier(results),
        }

    @app.get("/api/benchmark/leaderboard")
    @app.get("/benchmark/leaderboard")
    async def benchmark_leaderboard(session_id: str) -> dict[str, Any]:
        session = store.get_bench_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        results = store.list_bench_results(session_id)
        return {
            "session_id": session_id,
            "status": session.status,
            "leaderboard": build_leaderboard(results),
            "pareto": pareto_frontier(results),
        }

    # ------------------------------------------------------------------ pages
    detector_page = static_dir / "detector.html" if static_dir.is_dir() else None
    bench_page = static_dir / "bench.html" if static_dir.is_dir() else None
    landing_page = static_dir / "landing.html" if static_dir.is_dir() else None
    inspector_page = static_dir / "inspector.html" if static_dir.is_dir() else None

    @app.get("/detector", include_in_schema=False)
    @app.get("/freshness", include_in_schema=False)
    async def detector_page_route() -> FileResponse:
        if detector_page is None or not detector_page.is_file():
            raise HTTPException(status_code=404, detail="detector page not found")
        return FileResponse(detector_page)

    @app.get("/bench", include_in_schema=False)
    @app.get("/benchmark", include_in_schema=False)
    async def bench_page_route() -> FileResponse:
        if bench_page is None or not bench_page.is_file():
            raise HTTPException(status_code=404, detail="bench page not found")
        return FileResponse(bench_page)

    @app.get("/inspector", include_in_schema=False)
    @app.get("/inspector/{report_id}", include_in_schema=False)
    async def inspector_page_route(report_id: str | None = None) -> FileResponse:
        if inspector_page is None or not inspector_page.is_file():
            raise HTTPException(status_code=404, detail="inspector page not found")
        return FileResponse(inspector_page)

    # ------------------------------------------------------------------ static UI
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def index_page() -> FileResponse:
        if landing_page is not None and landing_page.is_file():
            return FileResponse(landing_page)
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="web UI not built")
        return FileResponse(index_file)

    @app.get("/research", include_in_schema=False)
    async def research_page() -> FileResponse:
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="web UI not built")
        return FileResponse(index_file)

    return app


app = create_app()



