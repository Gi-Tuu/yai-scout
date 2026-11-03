from __future__ import annotations

from pathlib import Path

from yai_scout.domain.models import Anchor, EvidenceSnapshot
from yai_scout.sources.anchor import replay_anchor_result
from yai_scout.store import Store


async def test_replay_scans_all_pages_for_one_url(tmp_path: Path):
    store = Store(":memory:")
    target_text = tmp_path / "target.txt"
    target_text.write_text("version 0.24.0", encoding="utf-8")
    store.save_snapshot(
        EvidenceSnapshot(
            id="snap_target",
            url="https://example.com/releases",
            text_path=str(target_text),
            published_at="2026-01-01T00:00:00Z",
            fetched_at="2026-01-01T00:00:00Z",
        )
    )
    for index in range(501):
        store.save_snapshot(
            EvidenceSnapshot(
                id=f"snap_newer_{index}",
                url="https://example.com/releases",
                text_path=str(target_text),
                published_at="2026-10-01T00:00:00Z",
                fetched_at="2026-10-01T00:00:00Z",
            )
        )
    anchor = Anchor(
        id="a1",
        claim_key="version #",
        url="https://example.com/releases",
        last_value="0.24.0",
    )
    result = await replay_anchor_result(
        store, anchor, "2026-02-01T00:00:00Z"
    )
    assert result is not None
    assert result.published_date == "2026-01-01T00:00:00Z"
    store.close()
