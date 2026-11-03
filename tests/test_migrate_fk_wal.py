from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.migrate_fk import migrate_copy

from yai_scout.domain.models import Anchor, ResearchTask
from yai_scout.store import Store


def test_migrator_includes_uncheckpointed_wal_data(tmp_path: Path):
    source = tmp_path / "wal-source.sqlite3"
    target = tmp_path / "wal-target.sqlite3"
    store = Store(source)
    store.create_task(ResearchTask(id="t1", question="q", as_of="2026-11-01"))
    store.close()

    # Keep a WAL with a committed row that is not copied by shutil.copy2.
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    anchor = Anchor(id="a_wal", claim_key="k", url="https://example.com")
    conn.execute(
        """INSERT INTO anchor
           (id, claim_key, claim_key_v2, claim_key_version, url, status,
            payload_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            anchor.id,
            anchor.claim_key,
            anchor.claim_key_v2,
            anchor.claim_key_version,
            anchor.url,
            anchor.status,
            anchor.model_dump_json(),
            anchor.last_verified_at,
        ),
    )
    conn.commit()
    assert Path(str(source) + "-wal").stat().st_size > 0

    migrate_copy(source, target)
    conn.close()

    target_conn = sqlite3.connect(target)
    assert (
        target_conn.execute("SELECT COUNT(*) FROM anchor WHERE id='a_wal'").fetchone()[0]
        == 1
    )
    target_conn.close()
