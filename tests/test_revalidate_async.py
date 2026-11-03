from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

from yai_scout.detector.revalidate import revalidate_due
from yai_scout.domain.models import Anchor, TemporalSensitivity
from yai_scout.sources.snapshot import save_snapshot
from yai_scout.store import Store


def _store_with_anchor(tmp_path: Path) -> Store:
    store = Store(":memory:")
    snapshot = save_snapshot(
        store,
        url="https://example.com/pricing",
        text="current price 1000",
        origin="live",
        snapshots_dir=tmp_path,
        published_at="2026-01-01T00:00:00Z",
    )
    store.save_anchor(
        Anchor(
            id="a1",
            claim_key="price #",
            url=snapshot.url,
            source_tier=1,
            last_value="500",
            content_hash="old-hash",
            published_at=snapshot.published_at,
            last_verified_at="2025-01-01T00:00:00Z",
            temporal_sensitivity=TemporalSensitivity.SENSITIVE,
        )
    )
    return store


async def test_revalidation_store_writes_do_not_block_event_loop(tmp_path: Path):
    store = _store_with_anchor(tmp_path)
    checked = asyncio.Event()
    observed = {"saw_event": False}
    original = store.save_anchor_observation

    def slow_save(observation):
        time.sleep(0.08)
        observed["saw_event"] = checked.is_set()
        return original(observation)

    store.save_anchor_observation = slow_save  # type: ignore[method-assign]

    async def ticker():
        await asyncio.sleep(0.01)
        checked.set()

    await asyncio.gather(
        revalidate_due(store, now=datetime(2026, 11, 1, tzinfo=UTC)),
        ticker(),
    )
    assert observed["saw_event"] is True
    store.close()
