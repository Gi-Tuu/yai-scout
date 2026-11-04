"""Tests for opt-in benchmark retention during app lifespan startup."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.domain.models import BenchSession
from yai_scout.store import Store


def _old_session(store: Store) -> None:
    store.create_bench_session(BenchSession(
        id="old-retention",
        status="done",  # type: ignore[arg-type]
        created_at="2020-01-01T00:00:00Z",
        finished_at="2020-01-01T00:00:00Z",
    ))


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "db_path": ":memory:",
        "openai_api_key": "",
        "tavily_api_key": "",
        "admin_token": "",
        "benchmark_retention_days": 0,
    }
    values.update(overrides)
    return Settings(**values)


def test_startup_prunes_when_retention_enabled(tmp_path: Path) -> None:
    store = Store(tmp_path / "retention.sqlite3")
    _old_session(store)
    app = create_app(settings=_settings(benchmark_retention_days=30), store=store)
    with TestClient(app):
        pass
    conn = sqlite3.connect(tmp_path / "retention.sqlite3")
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM bench_session WHERE id = ?",
            ("old-retention",),
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_startup_keeps_history_when_retention_disabled(tmp_path: Path) -> None:
    store = Store(tmp_path / "retention_off.sqlite3")
    _old_session(store)
    app = create_app(settings=_settings(benchmark_retention_days=0), store=store)
    with TestClient(app):
        pass
    conn = sqlite3.connect(tmp_path / "retention_off.sqlite3")
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM bench_session WHERE id = ?",
            ("old-retention",),
        ).fetchone()[0] == 1
    finally:
        conn.close()
