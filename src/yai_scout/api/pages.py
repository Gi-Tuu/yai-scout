"""Static HTML page routes.

Kept separate from the JSON API so app.py does not own both routing surfaces.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_pages(app: FastAPI, static_dir: Path) -> None:
    if not static_dir.is_dir():
        return
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    index_file = static_dir / "index.html"
    landing_page = static_dir / "landing.html"
    detector_page = static_dir / "detector.html"
    bench_page = static_dir / "bench.html"
    inspector_page = static_dir / "inspector.html"
    compare_page = static_dir / "compare.html"
    admin_page = static_dir / "admin-anchors.html"
    label_page = static_dir / "label.html"
    label_recover_page = static_dir / "label-recover.html"
    verdict_label_page = static_dir / "label-verdict.html"
    verdict_worksheet = (
        Path(__file__).resolve().parents[3]
        / "benchmarks"
        / "freshness_verdicts_private.json"
    )
    verdict_holdout = (
        Path(__file__).resolve().parents[3]
        / "benchmarks"
        / "freshness_verdicts_holdout_v2.json"
    )

    @app.get("/label/verdict", include_in_schema=False)
    async def verdict_label_route() -> FileResponse:
        if not verdict_label_page.is_file():
            raise HTTPException(status_code=404, detail="verdict label page not found")
        return FileResponse(verdict_label_page)

    @app.get("/label/verdict/worksheet", include_in_schema=False)
    async def verdict_worksheet_route(worksheet: str = "private") -> FileResponse:
        target = verdict_holdout if worksheet == "holdout" else verdict_worksheet
        if not target.is_file():
            raise HTTPException(status_code=404, detail="verdict worksheet not found")
        return FileResponse(target, media_type="application/json")

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

    @app.get("/label/recover", include_in_schema=False)
    async def label_recover_route() -> FileResponse:
        if label_recover_page is None or not label_recover_page.is_file():
            raise HTTPException(status_code=404, detail="recover page not found")
        return FileResponse(label_recover_page)

    @app.get("/label", include_in_schema=False)
    async def label_page_route() -> FileResponse:
        if label_page is None or not label_page.is_file():
            raise HTTPException(status_code=404, detail="label page not found")
        return FileResponse(label_page)

    @app.get("/admin", include_in_schema=False)
    async def admin_page_route() -> FileResponse:
        if admin_page is None or not admin_page.is_file():
            raise HTTPException(status_code=404, detail="admin page not found")
        return FileResponse(admin_page)

    @app.get("/compare", include_in_schema=False)
    async def compare_page_route() -> FileResponse:
        if compare_page is None or not compare_page.is_file():
            raise HTTPException(status_code=404, detail="compare page not found")
        return FileResponse(compare_page)

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
