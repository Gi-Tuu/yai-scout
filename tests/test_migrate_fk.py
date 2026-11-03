from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from scripts.migrate_fk import MigrationError, migrate_copy

from yai_scout.domain.models import Anchor, ResearchTask
from yai_scout.store import Store


def _source_db(path: Path) -> None:
    store = Store(path)
    store.create_task(ResearchTask(id="t1", question="q", as_of="2026-11-01"))
    store.save_anchor(
        Anchor(
            id="a1",
            claim_key="k",
            url="https://example.com",
            status="active",
        )
    )
    store.close()


def test_migrator_copies_data_and_adds_fks(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"
    _source_db(source)

    report = migrate_copy(source, target)
    assert report["foreign_key_check"] == "ok"
    assert report["before"] == report["after"]

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) FROM anchor").fetchone()[0] == 1
    fks = conn.execute("PRAGMA foreign_key_list(anchor_candidate)").fetchall()
    assert fks
    conn.execute("PRAGMA foreign_keys = ON")
    payload = '{"id":"c1","anchor_id":"missing","claim_key":"k"}'
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO anchor_candidate
               (id, anchor_id, status, payload_json, created_at)
               VALUES ('c1', 'missing', 'pending', ?, '2026-11-01')""",
            (payload,),
        )
    conn.close()


def test_migrator_rejects_orphans_without_touching_source(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"
    _source_db(source)
    conn = sqlite3.connect(source)
    conn.execute(
        """INSERT INTO source
           (id, task_id, url, canonical_url, domain, fetched_at)
           VALUES ('s1', 'missing_task', 'https://x', 'https://x', 'x', '2026-11-01')"""
    )
    conn.commit()
    conn.close()
    before = source.read_bytes()

    with pytest.raises(MigrationError):
        migrate_copy(source, target)
    assert source.read_bytes() == before
    assert not target.exists()
