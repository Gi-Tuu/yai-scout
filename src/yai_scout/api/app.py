"""FastAPI 应用：REST + SSE + 静态研究控制台。"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..domain.models import ResearchTask, RunEvent, TaskStatus
from ..pipeline.director import TERMINAL_EVENTS, ResearchDirector
from ..retrieval.tavily import TavilyClient
from ..store import Store


class CreateResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of: str | None = None


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

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await director.shutdown()
        await tavily.aclose()
        store.close()

    app = FastAPI(title=cfg.app_name, version=cfg.app_version, lifespan=lifespan)

    # ------------------------------------------------------------------ meta
    @app.get("/api/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "app": cfg.app_name,
            "version": cfg.app_version,
            "tavily": {"mode": tavily.mode, "authenticated": tavily.authenticated},
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

    # ------------------------------------------------------------------ static UI
    static_dir = cfg.web_dir / "static"
    index_file = static_dir / "index.html"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def index_page() -> FileResponse:
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="web UI not built")
        return FileResponse(index_file)

    return app


app = create_app()

