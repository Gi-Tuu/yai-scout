from __future__ import annotations

from pathlib import Path

from yai_scout.detector.snapshot_search import SnapshotSearcher
from yai_scout.domain.models import EvidenceSnapshot
from yai_scout.store import Store


async def test_snapshot_search_scans_beyond_first_page(tmp_path: Path):
    store = Store(":memory:")
    target_text = tmp_path / "target.txt"
    target_text.write_text("needle availability is 1000 credits", encoding="utf-8")
    store.save_snapshot(
        EvidenceSnapshot(
            id="snap_target",
            url="https://example.com/needle",
            text_path=str(target_text),
            published_at="2026-01-01T00:00:00Z",
            fetched_at="2026-01-01T00:00:00Z",
        )
    )
    for index in range(501):
        other = tmp_path / f"other_{index}.txt"
        other.write_text("unrelated content", encoding="utf-8")
        store.save_snapshot(
            EvidenceSnapshot(
                id=f"snap_other_{index}",
                url=f"https://other.example/{index}",
                text_path=str(other),
                published_at="2026-10-01T00:00:00Z",
                fetched_at="2026-10-01T00:00:00Z",
            )
        )

    searcher = SnapshotSearcher(store, target_time="2026-11-01")
    results, _ = await searcher.search("needle", max_results=1)
    assert results
    assert results[0].url == "https://example.com/needle"
    store.close()
