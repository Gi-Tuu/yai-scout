from pathlib import Path

from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.detector.snapshot_search import SnapshotSearcher
from yai_scout.domain.models import FreshnessStatus
from yai_scout.sources.snapshot import save_snapshot
from yai_scout.store import Store


def _store_with_releases(tmp_path: Path) -> Store:
    store = Store(":memory:")
    save_snapshot(
        store,
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0",
        text=(
            "release version v0.24.0\nname v0.24.0\n"
            "published_at 2026-10-24T00:00:00Z\n"
            "url https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0\n"
            "notes old release"
        ),
        origin="official_history",
        snapshots_dir=tmp_path,
        published_at="2026-10-24T00:00:00Z",
    )
    save_snapshot(
        store,
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0",
        text=(
            "release version v0.25.0\nname v0.25.0\n"
            "published_at 2026-10-31T00:00:00Z\n"
            "url https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0\n"
            "notes new release"
        ),
        origin="official_history",
        snapshots_dir=tmp_path,
        published_at="2026-10-31T00:00:00Z",
    )
    return store


async def test_replay_excludes_future_releases(tmp_path: Path):
    store = _store_with_releases(tmp_path)
    detector = StaleAnswerDetector(
        SnapshotSearcher(store, target_time="2026-10-25"),
        as_of="2026-10-25",
        max_claims=2,
        mode="replay",
    )
    report = await detector.detect("YAI Agent Core 当前版本是 0.25.0。")
    assert report.mode == "replay"
    assert report.verdicts
    assert report.verdicts[0].status in {
        FreshnessStatus.STALE,
        FreshnessStatus.INSUFFICIENT,
    }
    store.close()


async def test_replay_includes_release_after_publish(tmp_path: Path):
    store = _store_with_releases(tmp_path)
    detector = StaleAnswerDetector(
        SnapshotSearcher(store, target_time="2026-11-01"),
        as_of="2026-11-01",
        max_claims=2,
        mode="replay",
    )
    report = await detector.detect("YAI Agent Core 当前版本是 0.25.0。")
    assert report.mode == "replay"
    assert report.verdicts[0].status == FreshnessStatus.FRESH
    store.close()

