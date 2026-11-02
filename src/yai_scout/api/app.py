"""FastAPI 应用：REST + SSE + 静态研究控制台。"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..benchmark.adapters import HttpAdapter
from ..benchmark.dataset import load_dataset
from ..benchmark.manifest import result_hash as compute_result_hash
from ..benchmark.registry import build_adapters
from ..benchmark.runner import DEFAULT_AGENT_SPECS, BenchmarkRunner
from ..benchmark.scoring import leaderboard as build_leaderboard
from ..benchmark.scoring import pareto_frontier
from ..config import ROOT, Settings, get_settings
from ..detector.accuracy_gate import GateObservation, evaluate_gate
from ..detector.candidates import apply_candidate, independent_group_from_url
from ..detector.compare import claim_key, compare_reports
from ..detector.discovery import CachedDiscovery
from ..detector.receipt import build_report_receipt
from ..detector.revalidate import revalidate_due
from ..detector.service import StaleAnswerDetector
from ..detector.snapshot_search import SnapshotSearcher
from ..domain.models import (
    AgentSpec,
    Anchor,
    AnchorCandidate,
    CandidateEvidence,
    ResearchTask,
    RunEvent,
    TaskStatus,
    TemporalSensitivity,
    utcnow_iso,
)
from ..llm import LLMClient
from ..pipeline.director import TERMINAL_EVENTS, ResearchDirector
from ..retrieval.tavily import TavilyClient
from ..sources.anchor import live_anchor_result, replay_anchor_result
from ..sources.seed import seed_snapshots
from ..store import Store
from .limits import UsageLimiter
from .pages import register_pages


class CreateResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of: str | None = None


class DetectRequest(BaseModel):
    answer: str = Field(min_length=10, max_length=8000)
    as_of: str | None = None
    max_claims: int = Field(default=6, ge=1, le=12)
    mode: Literal["live", "replay"] = "live"
    use_anchors: bool = True


class AnchorCreate(BaseModel):
    claim_text: str = Field(min_length=3, max_length=800)
    url: str = Field(min_length=5, max_length=2000)
    last_value: str = ""
    content_hash: str = ""
    source_tier: int = Field(default=3, ge=1, le=4)
    published_at: str | None = None
    temporal_sensitivity: TemporalSensitivity | None = None


class RevalidateRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class ObservationInput(BaseModel):
    url: str
    source_tier: int = Field(default=3, ge=1, le=4)
    independent_group: str = ""
    value: str = ""
    published_at: str | None = None
    content_hash: str = ""
    reachable: bool = True


class CandidateCreate(BaseModel):
    observations: list[ObservationInput] = Field(default_factory=list)


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
    llm_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    static_dir = cfg.web_dir / "static"
    store = store or Store(cfg.db_path)
    seed_path = Path(cfg.snapshots_seed)
    if not seed_path.is_absolute():
        seed_path = ROOT / seed_path
    seed_snapshots(store, seed_path, Path(cfg.db_path).parent / "snapshots")
    tavily = tavily or TavilyClient(
        cfg.tavily_api_key,
        base_url=cfg.tavily_base_url,
        allow_keyless=cfg.tavily_allow_keyless,
        timeout=cfg.tavily_timeout_seconds,
        search_depth=cfg.search_depth,
        max_results=cfg.max_results_per_query,
    )
    director = ResearchDirector(store, tavily, cfg)
    llm_cfg = cfg.llm_connection()
    llm = LLMClient(
        str(llm_cfg["api_key"]),
        base_url=str(llm_cfg["base_url"]),
        model=str(llm_cfg["model"]),
        require_key=bool(llm_cfg["require_key"]),
        gateway=str(llm_cfg["gateway"]),
        transport=llm_transport,
    )
    detector = StaleAnswerDetector(
        tavily,
        as_of=cfg.default_as_of,
        max_claims=6,
        concurrency=3,
        llm=llm,
    )
    adapters = build_adapters(tavily, llm)
    agent_specs = {spec.id: spec for spec in DEFAULT_AGENT_SPECS}
    if cfg.http_agent_url:
        adapters["external_http"] = HttpAdapter(
            "external_http", "External HTTP Agent", cfg.http_agent_url
        )
        agent_specs["external_http"] = AgentSpec(
            id="external_http",
            name="External HTTP Agent",
            kind="http",
            description=f"scout-adapter/1.0 → {cfg.http_agent_url}",
            config={"endpoint": cfg.http_agent_url},
        )
    runner = BenchmarkRunner(
        store, adapters, detector, cfg=cfg, agent_specs=agent_specs
    )
    discovery = CachedDiscovery(
        tavily,
        ttl_seconds=cfg.anchor_discovery_ttl_seconds,
        daily_budget=cfg.anchor_discovery_daily_budget,
        max_cache_entries=cfg.anchor_discovery_cache_entries,
    )
    limiter = UsageLimiter(
        per_minute=cfg.rate_limit_per_minute,
        daily={
            "detector": cfg.daily_detector_limit,
            "benchmark": cfg.daily_benchmark_limit,
            "anchor": cfg.daily_anchor_limit,
            "research": cfg.daily_research_limit,
        },
    )

    def guard_cost(request: Request, bucket: str) -> None:
        if not cfg.demo_limits_enabled:
            return
        client = UsageLimiter.client_key(
            dict(request.headers), request.client.host if request.client else "unknown"
        )
        allowed, retry = limiter.check(bucket, client)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"rate limit exceeded for {bucket}; retry in {retry}s",
                headers={"Retry-After": str(retry)},
            )

    def validated_as_of(value: str | None) -> str:
        if not value:
            return datetime.now(UTC).date().isoformat()
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid as_of") from exc
        return value

    def session_id(request: Request, response: Response | None = None) -> str:
        sid = request.cookies.get("scout_sid")
        if not sid:
            sid = secrets.token_urlsafe(24)
            if response is not None:
                response.set_cookie(
                    "scout_sid",
                    sid,
                    max_age=60 * 60 * 24 * 30,
                    httponly=True,
                    samesite="lax",
                    secure=request.url.scheme == "https",
                )
        return sid

    def is_admin(request: Request) -> bool:
        return bool(cfg.admin_token) and request.headers.get(
            "authorization"
        ) == f"Bearer {cfg.admin_token}"

    def can_access(owner_id: str, request: Request) -> bool:
        # Legacy/demo rows have owner_id="" and remain public.
        return not owner_id or owner_id == session_id(request) or is_admin(request)

    benchmark_enabled = cfg.scout_mode in {"all", "benchmark"}
    freshness_enabled = cfg.scout_mode in {"all", "freshness"}

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        store.mark_interrupted_work()
        yield
        await director.shutdown()
        await runner.shutdown()
        await tavily.aclose()
        await llm.aclose()
        store.close()

    app = FastAPI(title=cfg.app_name, version=cfg.app_version, lifespan=lifespan)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'",
        )
        return response

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
            "snapshots": len(
                await asyncio.to_thread(store.list_snapshots, limit=1000)
            ),
            "discovery": discovery.usage(),
            "build": os.environ.get("RENDER_GIT_COMMIT", "dev")[:12],
            "limits": limiter.usage(),
            "tavily": {"mode": tavily.mode, "authenticated": tavily.authenticated},
            "llm": {
                "available": llm.available,
                "gateway": llm.gateway,
                "model": llm.model,
            },
        }

    # ------------------------------------------------------------------ research
    @app.post("/api/research", status_code=202)
    async def create_research(
        payload: CreateResearchRequest, request: Request, response: Response
    ) -> dict[str, Any]:
        if not cfg.research_enabled:
            raise HTTPException(status_code=404, detail="research disabled")
        guard_cost(request, "research")
        if director.active_count() >= cfg.max_active_research_tasks:
            raise HTTPException(
                status_code=429,
                detail="too many active research tasks; retry later",
                headers={"Retry-After": "30"},
            )
        task = ResearchTask(
            id=f"task_{uuid.uuid4().hex[:12]}",
            owner_id=session_id(request, response),
            question=" ".join(payload.question.split()),
            as_of=validated_as_of(payload.as_of),
        )
        await asyncio.to_thread(store.create_task, task)
        director.start(task)
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
                s.model_dump(mode="json")
                for s in await asyncio.to_thread(store.list_sources, task_id)
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
        task = store.get_task(task_id)
        if task is None or not can_access(task.owner_id, request):
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
    async def detect(
        payload: DetectRequest, request: Request, response: Response
    ) -> dict[str, Any]:
        guard_cost(request, "detector")
        owner_id = session_id(request, response)
        if payload.mode == "replay" and not payload.as_of:
            raise HTTPException(status_code=400, detail="replay requires explicit as_of")
        effective_as_of = validated_as_of(payload.as_of)
        anchors = (
            await asyncio.to_thread(store.list_anchors)
            if payload.use_anchors
            else []
        )
        if payload.mode == "replay":
            async def _anchor_fetcher(anchor: Anchor, target: str) -> Any:
                return await replay_anchor_result(store, anchor, target)

            replay = StaleAnswerDetector(
                SnapshotSearcher(store, target_time=effective_as_of),
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                concurrency=3,
                llm=llm,
                mode="replay",
                anchor_fetcher=_anchor_fetcher,
            )
            report = await replay.detect(
                payload.answer, as_of=effective_as_of, anchors=anchors
            )
        elif cfg.anchor_live_fetch and anchors:
            allowlist = {
                item.strip().lower()
                for item in cfg.anchor_allowlist.split(",")
                if item.strip()
            }

            async def _live_anchor(anchor: Anchor, target: str) -> Any:
                return await live_anchor_result(anchor, allowlist)

            live_detector = StaleAnswerDetector(
                tavily,
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                concurrency=3,
                llm=llm,
                mode="live",
                anchor_fetcher=_live_anchor,
            )
            report = await live_detector.detect(
                payload.answer,
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                anchors=anchors,
            )
        else:
            report = await detector.detect(
                payload.answer,
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                anchors=anchors,
            )
        report = report.model_copy(update={"owner_id": owner_id})
        await asyncio.to_thread(store.save_detector_report, report)
        return report.model_dump(mode="json")

    @app.get("/api/detector/{report_id}")
    @app.get("/freshness/reports/{report_id}")
    async def get_detector_report(report_id: str, request: Request) -> dict[str, Any]:
        report = await asyncio.to_thread(store.get_detector_report, report_id)
        if report is None or not can_access(report.owner_id, request):
            raise HTTPException(status_code=404, detail="report not found")
        return report.model_dump(mode="json")

    @app.get("/freshness/reports/{report_id}/receipt")
    async def get_receipt(report_id: str, request: Request) -> dict[str, Any]:
        report = await asyncio.to_thread(store.get_detector_report, report_id)
        if report is None or not can_access(report.owner_id, request):
            raise HTTPException(status_code=404, detail="report not found")
        return build_report_receipt(report).model_dump(mode="json")

    @app.get("/freshness/reports")
    async def list_detector_reports(
        request: Request, limit: int = 20
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        if is_admin(request):
            reports = await asyncio.to_thread(
                store.list_detector_reports, limit=limit
            )
        else:
            reports = await asyncio.to_thread(
                store.list_detector_reports,
                limit=limit,
                owner_id=session_id(request),
            )
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
    async def export_detector_report(
        report_id: str, request: Request
    ) -> dict[str, Any]:
        report = await asyncio.to_thread(store.get_detector_report, report_id)
        if report is None or not can_access(report.owner_id, request):
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

    @app.post("/freshness/anchors", status_code=201)
    async def create_anchor(payload: AnchorCreate, request: Request) -> dict[str, Any]:
        guard_cost(request, "anchor")
        if not cfg.public_anchor_writes and not is_admin(request):
            raise HTTPException(status_code=403, detail="anchor writes require admin")
        parsed = urlsplit(payload.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise HTTPException(status_code=400, detail="anchor url must be http(s)")
        if parsed.username or parsed.password:
            raise HTTPException(status_code=400, detail="anchor url must not contain credentials")
        allowed_hosts = {
            item.strip().lower()
            for item in cfg.anchor_create_allowlist.split(",")
            if item.strip()
        }
        if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
            raise HTTPException(status_code=400, detail="anchor host not allowed")
        snapshots = await asyncio.to_thread(
            store.list_snapshots_for_url, payload.url, 1
        )
        latest = snapshots[0] if snapshots else None
        anchor = Anchor(
            id=f"anc_{uuid.uuid4().hex[:12]}",
            claim_key=claim_key(payload.claim_text),
            claim_text=payload.claim_text,
            url=payload.url,
            source_tier=payload.source_tier,
            last_value=payload.last_value,
            content_hash=payload.content_hash or (latest.content_hash if latest else ""),
            published_at=payload.published_at or (latest.published_at if latest else None),
            temporal_sensitivity=payload.temporal_sensitivity,
        )
        await asyncio.to_thread(store.save_anchor, anchor)
        return anchor.model_dump(mode="json")

    @app.post("/admin/anchors/revalidate")
    async def admin_revalidate(
        request: Request, payload: RevalidateRequest | None = None
    ) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        fetcher = None
        if cfg.anchor_live_fetch:
            allowlist = {
                item.strip().lower()
                for item in cfg.anchor_allowlist.split(",")
                if item.strip()
            }

            async def _live(anchor: Anchor, target: str) -> Any:
                return await live_anchor_result(anchor, allowlist)

            fetcher = _live
        observations = await revalidate_due(
            store,
            fetcher=fetcher,
            discovery=discovery,
            limit=payload.limit if payload else 50,
            auto_update=cfg.accuracy_auto_update,
        )
        return {
            "checked": len(observations),
            "changed": sum(1 for item in observations if item.status == "changed"),
            "unreachable": sum(1 for item in observations if item.status == "unreachable"),
            "observations": [item.model_dump(mode="json") for item in observations],
        }

    @app.get("/freshness/anchors")
    async def list_anchors(claim_key: str | None = None) -> dict[str, Any]:
        anchors = await asyncio.to_thread(store.list_anchors, claim_key=claim_key)
        return {"anchors": [anchor.model_dump(mode="json") for anchor in anchors]}

    @app.post("/admin/anchors/{anchor_id}/candidates", status_code=201)
    async def create_anchor_candidate(
        anchor_id: str, payload: CandidateCreate, request: Request
    ) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        anchor = await asyncio.to_thread(store.get_anchor, anchor_id)
        if anchor is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        observations = [
            GateObservation(
                url=item.url,
                source_tier=item.source_tier,
                independent_group=item.independent_group
                or independent_group_from_url(item.url),
                value=item.value,
                published_at=item.published_at,
                content_hash=item.content_hash,
                reachable=item.reachable,
            )
            for item in payload.observations
        ]
        gate = evaluate_gate(
            anchor_value=anchor.last_value,
            anchor_published_at=anchor.published_at,
            observations=observations,
            claim_text=anchor.claim_text,
        )
        existing = await asyncio.to_thread(
            store.find_anchor_candidate,
            anchor.id,
            gate.normalized_new,
            gate.decision.value,
        )
        if existing is not None:
            return existing.model_dump(mode="json")
        reachable = [item for item in observations if item.reachable and item.value]
        best = max(reachable, key=lambda item: item.published_at or "") if reachable else None
        candidate = AnchorCandidate(
            id=f"cand_{uuid.uuid4().hex[:12]}",
            anchor_id=anchor.id,
            claim_key=anchor.claim_key,
            old_value=anchor.last_value,
            new_value=best.value if best else "",
            normalized_old=gate.normalized_old,
            normalized_new=gate.normalized_new,
            evidence=[
                CandidateEvidence(
                    url=item.url,
                    source_tier=item.source_tier,
                    independent_group=item.independent_group,
                    value=item.value,
                    published_at=item.published_at,
                    content_hash=item.content_hash,
                )
                for item in observations
            ],
            gate_decision=gate.decision.value,
            gate_reason=gate.reason,
            gate_version="accuracy-gate-v0",
            confidence=gate.confidence,
        )
        await asyncio.to_thread(store.save_anchor_candidate, candidate)

        if gate.decision.value == "no_change":
            candidate = candidate.model_copy(
                update={"accuracy_status": "no_change", "decided_at": utcnow_iso()}
            )
            await asyncio.to_thread(store.update_anchor_candidate, candidate)
        elif gate.decision.value == "reject":
            candidate = candidate.model_copy(
                update={
                    "accuracy_status": "rejected",
                    "decided_at": utcnow_iso(),
                    "decided_by": "gate",
                }
            )
            await asyncio.to_thread(store.update_anchor_candidate, candidate)
        elif gate.decision.value == "auto_update" and cfg.accuracy_auto_update:
            if best is None:
                raise HTTPException(status_code=400, detail="no usable observation")
            candidate = await asyncio.to_thread(
                apply_candidate,
                store,
                candidate,
                status="auto_applied",
                decided_by="auto-gate",
            )
        return candidate.model_dump(mode="json")

    @app.get("/admin/anchors/candidates")
    async def list_anchor_candidates(
        request: Request, status: str | None = None
    ) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        candidates = await asyncio.to_thread(
            store.list_anchor_candidates, status=status
        )
        return {"candidates": [item.model_dump(mode="json") for item in candidates]}

    @app.post("/admin/anchors/candidates/{candidate_id}/approve")
    async def approve_anchor_candidate(
        candidate_id: str, request: Request
    ) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        candidate = await asyncio.to_thread(store.get_anchor_candidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        if candidate.accuracy_status != "pending":
            raise HTTPException(status_code=409, detail="candidate is not pending")
        anchor = await asyncio.to_thread(store.get_anchor, candidate.anchor_id)
        if anchor is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        if anchor.status != "active":
            raise HTTPException(status_code=409, detail="anchor is no longer active")
        if not candidate.evidence:
            raise HTTPException(status_code=400, detail="candidate has no evidence")
        updated = await asyncio.to_thread(
            apply_candidate,
            store,
            candidate,
            status="approved",
            decided_by="admin",
        )
        return updated.model_dump(mode="json")

    @app.post("/admin/anchors/candidates/{candidate_id}/reject")
    async def reject_anchor_candidate(
        candidate_id: str, request: Request
    ) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        candidate = await asyncio.to_thread(store.get_anchor_candidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        if candidate.accuracy_status != "pending":
            raise HTTPException(status_code=409, detail="candidate is not pending")
        updated = candidate.model_copy(
            update={
                "accuracy_status": "rejected",
                "decided_at": utcnow_iso(),
                "decided_by": "admin",
            }
        )
        await asyncio.to_thread(store.update_anchor_candidate, updated)
        return updated.model_dump(mode="json")

    @app.get("/admin/anchors/audit")
    async def admin_anchor_audit(request: Request, limit: int = 100) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        audit = await asyncio.to_thread(
            store.list_anchor_audit, limit=max(1, min(limit, 500))
        )
        return {"audit": audit}

    @app.get("/admin/anchors")
    async def admin_list_anchors(request: Request) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        anchors = await asyncio.to_thread(
            store.list_anchors, active_only=False, limit=500
        )
        return {"anchors": [anchor.model_dump(mode="json") for anchor in anchors]}

    @app.post("/admin/anchors/{anchor_id}/rollback")
    async def admin_rollback_anchor(
        anchor_id: str, request: Request
    ) -> dict[str, Any]:
        if not cfg.admin_token:
            raise HTTPException(status_code=404, detail="admin endpoint disabled")
        if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
            raise HTTPException(status_code=401, detail="unauthorized")
        anchor = await asyncio.to_thread(store.get_anchor, anchor_id)
        if anchor is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        if anchor.status != "active" or not anchor.supersedes:
            raise HTTPException(
                status_code=409, detail="anchor is not an active replacement"
            )
        result = await asyncio.to_thread(store.rollback_anchor, anchor_id)
        if result is None:
            raise HTTPException(status_code=409, detail="rollback failed")
        restored, rolled_back = result
        rolled_candidates = await asyncio.to_thread(
            store.mark_candidates_rolled_back, rolled_back.id
        )
        audit_id = await asyncio.to_thread(
            store.save_anchor_audit,
            "rollback",
            rolled_back.id,
            related_id=restored.id,
            details={"rolled_back_candidates": rolled_candidates},
        )
        return {
            "restored": restored.model_dump(mode="json"),
            "rolled_back": rolled_back.model_dump(mode="json"),
            "rolled_back_candidates": rolled_candidates,
            "audit_id": audit_id,
        }

    @app.get("/freshness/compare")
    async def compare_freshness_reports(
        left_id: str, right_id: str, request: Request
    ) -> dict[str, Any]:
        left, right = await asyncio.gather(
            asyncio.to_thread(store.get_detector_report, left_id),
            asyncio.to_thread(store.get_detector_report, right_id),
        )
        if (
            left is None
            or right is None
            or not can_access(left.owner_id, request)
            or not can_access(right.owner_id, request)
        ):
            raise HTTPException(status_code=404, detail="report not found")
        return compare_reports(left, right).model_dump(mode="json")

    # ------------------------------------------------------------------ benchmark
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
        session = await asyncio.to_thread(store.get_bench_session, session_id)
        if session is None or not can_access(session.owner_id, request):
            raise HTTPException(status_code=404, detail="session not found")
        results = await asyncio.to_thread(store.list_bench_results, session_id)
        return {
            "session": session.model_dump(mode="json"),
            "results": [result.model_dump(mode="json") for result in results],
            "leaderboard": build_leaderboard(results),
            "pareto": pareto_frontier(results),
        }

    @app.get("/benchmark/runs/{session_id}/verify")
    @app.get("/api/benchmark/runs/{session_id}/verify")
    async def verify_benchmark_run(session_id: str, request: Request) -> dict[str, Any]:
        session = await asyncio.to_thread(store.get_bench_session, session_id)
        if session is None or not can_access(session.owner_id, request):
            raise HTTPException(status_code=404, detail="session not found")
        results = await asyncio.to_thread(store.list_bench_results, session_id)
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
        session = await asyncio.to_thread(store.get_bench_session, session_id)
        if session is None or not can_access(session.owner_id, request):
            raise HTTPException(status_code=404, detail="session not found")
        results = await asyncio.to_thread(store.list_bench_results, session_id)
        return {
            "session_id": session_id,
            "status": session.status,
            "leaderboard": build_leaderboard(results),
            "pareto": pareto_frontier(results),
        }

    register_pages(app, static_dir)

    return app


app = create_app()


































