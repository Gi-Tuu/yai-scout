"""Research task JSON/SSE routes."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import Settings
from ..domain.models import ResearchTask, RunEvent
from ..pipeline.director import TERMINAL_EVENTS, ResearchDirector
from ..store import Store
from .streams import StreamLimiter


class CreateResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of: str | None = None


def _sse(event: RunEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"id: {event.seq}\nevent: {event.type}\ndata: {data}\n\n"


def register_research_routes(
    app: FastAPI,
    *,
    cfg: Settings,
    store: Store,
    director: ResearchDirector,
    guard_cost: Callable[[Request, str], None],
    session_id: Callable[..., str],
    can_access: Callable[[str, Request], bool],
    validated_as_of: Callable[[str | None], str],
    is_admin: Callable[[Request], bool],
    stream_limiter: StreamLimiter,
) -> None:
    @app.post("/api/research", status_code=202)
    async def create_research(
        payload: CreateResearchRequest, request: Request, response: Response
    ) -> dict[str, Any]:
        if not cfg.research_enabled:
            raise HTTPException(status_code=404, detail="research disabled")
        guard_cost(request, "research")
        task = ResearchTask(
            id=f"task_{uuid.uuid4().hex[:12]}",
            owner_id=session_id(request, response),
            question=" ".join(payload.question.split()),
            as_of=validated_as_of(payload.as_of),
        )
        accepted = await director.submit(
            task, max_active=cfg.max_active_research_tasks
        )
        if not accepted:
            raise HTTPException(
                status_code=429,
                detail="too many active research tasks; retry later",
                headers={"Retry-After": "30"},
            )
        return {
            "task": task.model_dump(mode="json"),
            "events_url": f"/api/research/{task.id}/events",
        }

    @app.get("/api/research")
    async def list_research(request: Request, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        if is_admin(request):
            tasks = await asyncio.to_thread(store.list_tasks, limit=limit)
        else:
            tasks = await asyncio.to_thread(
                store.list_tasks,
                limit=limit,
                owner_id=session_id(request),
            )
        return {"tasks": [task.model_dump(mode="json") for task in tasks]}

    @app.get("/api/research/{task_id}")
    async def get_research(task_id: str, request: Request) -> dict[str, Any]:
        task = await asyncio.to_thread(store.get_task, task_id)
        if task is None or not can_access(task.owner_id, request):
            raise HTTPException(status_code=404, detail="task not found")
        plan = await asyncio.to_thread(store.get_plan, task_id)
        credits, usd = await asyncio.to_thread(store.cost_sum, task_id)
        return {
            "task": task.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json") if plan else None,
            "sources": [
                source.model_dump(mode="json")
                for source in await asyncio.to_thread(store.list_sources, task_id)
            ],
            "cost": {"credits": round(credits, 3), "usd": round(usd, 4)},
            "event_count": len(
                await asyncio.to_thread(store.list_events, task_id, 0, 10000)
            ),
        }

    @app.post("/api/research/{task_id}/cancel")
    async def cancel_research(task_id: str, request: Request) -> dict[str, Any]:
        task = await asyncio.to_thread(store.get_task, task_id)
        if task is None or not can_access(task.owner_id, request):
            raise HTTPException(status_code=404, detail="task not found")
        cancelled = await director.cancel(task_id)
        return {"cancelled": cancelled}

    @app.get("/api/research/{task_id}/events")
    async def research_events(task_id: str, request: Request) -> StreamingResponse:
        task = await asyncio.to_thread(store.get_task, task_id)
        if task is None or not can_access(task.owner_id, request):
            raise HTTPException(status_code=404, detail="task not found")
        cursor = 0
        header = request.headers.get("last-event-id") or request.headers.get(
            "Last-Event-ID"
        )
        if header and header.isdigit():
            cursor = int(header)
        if not stream_limiter.acquire(task_id):
            raise HTTPException(
                status_code=429,
                detail="too many active event streams",
                headers={"Retry-After": "10"},
            )

        async def stream() -> AsyncIterator[str]:
            nonlocal cursor
            idle = 0.0
            try:
                while True:
                    if await request.is_disconnected():
                        return
                    events = await asyncio.to_thread(
                        store.list_events, task_id, cursor, 200
                    )
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
                        task = await asyncio.to_thread(store.get_task, task_id)
                        if task is not None and task.status.value in {
                            "delivered",
                            "failed",
                            "cancelled",
                        }:
                            yield (
                                "event: stream_closed\n"
                                f"data: {json.dumps({'status': task.status.value})}\n\n"
                            )
                            return
            finally:
                stream_limiter.release(task_id)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
