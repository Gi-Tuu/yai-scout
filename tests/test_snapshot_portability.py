from __future__ import annotations

from pathlib import Path

import pytest

from yai_scout.sources.anchor import replay_anchor_result
from yai_scout.sources.snapshot import save_snapshot
from yai_scout.store import Store


@pytest.mark.asyncio
async def test_snapshot_path_is_relative_and_replayable(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    snapshot = save_snapshot(
        store,
        url="https://example.com/releases",
        text="release 1.0 published 2026-01-01",
        origin="official_history",
        snapshots_dir=tmp_path / "snapshots",
        published_at="2026-01-01T00:00:00Z",
    )
    assert not Path(snapshot.text_path).is_absolute()
    assert (tmp_path / snapshot.text_path).is_file()
    from yai_scout.domain.models import Anchor

    anchor = Anchor(id="a", claim_key="k", claim_key_v2="v", claim_key_version=2, url=snapshot.url)
    result = await replay_anchor_result(store, anchor, "2026-02-01T00:00:00Z")
    assert result is not None
    assert "release 1.0" in result.content
    store.close()
