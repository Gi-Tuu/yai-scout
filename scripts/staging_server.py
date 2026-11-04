"""Local staging server for repeatable load tests.

Uses a separate SQLite database, packaged snapshots and a deterministic Fake
Tavily client. No real Tavily/LLM calls are made.
"""
from __future__ import annotations

import os
from pathlib import Path

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.store import Store

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "staging" / "staging.sqlite3"


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return (
            [
                SearchResult(
                    title="Python End-of-Life Dates",
                    url="https://endoflife.date/python",
                    content="3.12 | 2023\n3.15 | latest",
                )
            ],
            0.0,
        )

    async def aclose(self) -> None:
        return None


def build_app(db_path: Path):
    settings = Settings(
        _env_file=None,
        db_path=db_path,
        snapshots_seed=str(ROOT / "benchmarks" / "snapshots.json"),
        tavily_api_key="",
        openai_api_key="",
        bifrost_base_url="",
        demo_limits_enabled=False,
    )
    store = Store(db_path)
    return create_app(settings=settings, store=store, tavily=FakeTavily())


def main() -> int:
    db_path = Path(os.environ.get("STAGING_DB", DEFAULT_DB))
    if os.environ.get("STAGING_RESET", "1") == "1":
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(db_path) + suffix)
            if candidate.exists():
                candidate.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    app = build_app(db_path)

    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("STAGING_HOST", "0.0.0.0"),
        port=int(os.environ.get("STAGING_PORT", "8020")),
        log_level="warning",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
