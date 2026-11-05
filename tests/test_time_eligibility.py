from __future__ import annotations

from pathlib import Path

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.detector.snapshot_search import SnapshotSearcher
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    FreshnessStatus,
    TemporalSensitivity,
)
from yai_scout.sources.snapshot import save_snapshot
from yai_scout.store import Store


def test_date_only_as_of_includes_same_day() -> None:
    target = as_of_datetime("2026-11-05")
    assert target.hour == 23
    claim = Claim(
        id="c",
        text="price is 1000",
        type=ClaimType.PRICING,
        target_time="2026-11-05",
        numbers=["1000"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )
    evidence = [
        EvidenceRef(
            url="https://example.com/price",
            published_at="2026-11-05T12:00:00Z",
            tier=1,
            relation="supports",
        )
    ]
    verdict = score_claim(claim, evidence, as_of=target, allow_future=False)
    assert verdict.status is FreshnessStatus.FRESH


def test_low_authority_mentions_do_not_hide_authority_contradiction() -> None:
    claim = Claim(
        id="c",
        text="YAI 当前版本是 0.24.0",
        type=ClaimType.VERSION,
        numbers=["0.24.0"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )
    evidence = [
        EvidenceRef(
            url="https://official.example/releases",
            published_at="2026-11-01T00:00:00Z",
            tier=1,
            relation="contradicts",
        ),
        EvidenceRef(
            url="https://blog.example/post",
            published_at="2026-11-04T00:00:00Z",
            tier=4,
            relation="mentions",
        ),
    ]
    verdict = score_claim(
        claim,
        evidence,
        as_of=as_of_datetime("2026-11-05"),
        allow_future=False,
    )
    assert verdict.status is FreshnessStatus.STALE


async def test_manual_future_content_is_not_replay_eligible(tmp_path: Path) -> None:
    store = Store(":memory:")
    save_snapshot(
        store,
        url="https://example.com/future",
        text="version 9.0 was released in 2026-11",
        origin="manual",
        snapshots_dir=tmp_path,
        published_at="2026-01-01T00:00:00Z",
    )
    searcher = SnapshotSearcher(store, target_time="2026-02-01T00:00:00Z")
    results, _ = await searcher.search("version 9.0", max_results=4)
    assert results == []
    store.close()


async def test_official_history_snapshot_still_replays(tmp_path: Path) -> None:
    store = Store(":memory:")
    save_snapshot(
        store,
        url="https://example.com/official",
        text="release zeta alpha published 2026-01-01",
        origin="official_history",
        snapshots_dir=tmp_path,
        published_at="2026-01-01T00:00:00Z",
    )
    searcher = SnapshotSearcher(store, target_time="2026-02-01T00:00:00Z")
    results, _ = await searcher.search("zeta alpha", max_results=4)
    assert results
    store.close()
