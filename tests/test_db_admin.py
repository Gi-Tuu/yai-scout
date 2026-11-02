from __future__ import annotations

from pathlib import Path

import pytest
from scripts.db_admin import backup, integrity_check, restore

from yai_scout.domain.models import Anchor
from yai_scout.store import Store


def _create_db(path: Path) -> None:
    store = Store(path)
    store.save_anchor(
        Anchor(id="anc_1", claim_key="k", url="https://example.com", last_value="v")
    )
    store.close()


def test_backup_and_restore(tmp_path: Path):
    db = tmp_path / "scout.sqlite3"
    out = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _create_db(db)

    backup(db, out)
    assert integrity_check(out) == "ok"
    restore(out, restored, force=False)
    assert integrity_check(restored) == "ok"

    store = Store(restored)
    assert store.get_anchor("anc_1") is not None
    store.close()


def test_restore_refuses_existing_without_force(tmp_path: Path):
    db = tmp_path / "scout.sqlite3"
    out = tmp_path / "backup.sqlite3"
    _create_db(db)
    backup(db, out)
    with pytest.raises(SystemExit):
        restore(out, db, force=False)
