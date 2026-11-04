"""FastAPI 应用：REST + SSE + 静态研究控制台。"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ..benchmark.adapters import HttpAdapter
from ..benchmark.registry import build_adapters
from ..benchmark.runner import DEFAULT_AGENT_SPECS, BenchmarkRunner
from ..config import ROOT, Settings, get_settings
from ..detector.discovery import CachedDiscovery
from ..detector.service import StaleAnswerDetector
from ..domain.models import (
    AgentSpec,
)
from ..llm import LLMClient
from ..pipeline.director import ResearchDirector
from ..retrieval.tavily import TavilyClient
from ..sources.page import fetch_page
from ..sources.seed import seed_snapshots
from ..store import Store
from .admin_routes import register_admin_routes
from .benchmark_routes import register_benchmark_routes
from .freshness_routes import register_freshness_routes
from .limits import UsageLimiter
from .pages import register_pages
from .research_routes import register_research_routes

logger = logging.getLogger(__name__)


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
    page_allowlist = cfg.full_page_hosts()

    async def _page_fetcher(result: Any) -> Any:
        return await fetch_page(result.url, page_allowlist)

    page_fetcher = (
        _page_fetcher
        if cfg.full_page_fetch_enabled and page_allowlist
        else None
    )
    detector = StaleAnswerDetector(
        tavily,
        as_of=cfg.default_as_of,
        max_claims=6,
        concurrency=3,
        llm=llm,
        page_fetcher=page_fetcher,
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
        retention: dict[str, object] = {
            "enabled": cfg.benchmark_retention_days > 0,
            "days": cfg.benchmark_retention_days,
            "result": None,
            "error": None,
        }
        if cfg.benchmark_retention_days > 0:
            try:
                retention["result"] = store.prune_benchmarks(
                    days=cfg.benchmark_retention_days
                )
            except Exception:  # noqa: BLE001 - startup must continue
                retention["error"] = "retention_failed"
                logger.warning("benchmark retention failed", exc_info=True)
        _app.state.benchmark_retention = retention
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
            "script-src 'self'; "
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
    async def healthz() -> JSONResponse:
        try:
            await asyncio.to_thread(store.ping)
            snapshots = len(await asyncio.to_thread(store.list_snapshots, limit=1000))
        except Exception as exc:  # noqa: BLE001 - health endpoint must report failure
            return JSONResponse(
                {"status": "error", "database": "unavailable",
                 "error": f"{type(exc).__name__}: {exc}"},
                status_code=503,
            )
        return JSONResponse({
            "status": "ok",
            "app": cfg.app_name,
            "version": cfg.app_version,
            "mode": cfg.scout_mode,
            "snapshots": snapshots,
            "retention": getattr(
                app.state, "benchmark_retention",
                {"enabled": cfg.benchmark_retention_days > 0,
                 "days": cfg.benchmark_retention_days, "result": None, "error": None},
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
        })

    register_research_routes(
        app,
        cfg=cfg,
        store=store,
        director=director,
        guard_cost=guard_cost,
        session_id=session_id,
        can_access=can_access,
        validated_as_of=validated_as_of,
        is_admin=is_admin,
    )

    register_freshness_routes(
        app,
        cfg=cfg,
        store=store,
        tavily=tavily,
        llm=llm,
        detector=detector,
        guard_cost=guard_cost,
        session_id=session_id,
        can_access=can_access,
        is_admin=is_admin,
        validated_as_of=validated_as_of,
        page_fetcher=page_fetcher,
    )

    register_admin_routes(
        app,
        cfg=cfg,
        store=store,
        discovery=discovery,
    )

    register_benchmark_routes(
        app,
        cfg=cfg,
        store=store,
        runner=runner,
        guard_cost=guard_cost,
        can_access=can_access,
        session_id=session_id,
        is_admin=is_admin,
    )

    register_pages(app, static_dir)

    return app


app = create_app()


































