"""Read-time TTL revalidation for anchors (no in-process scheduler).

Design: due anchors are selected by sensitivity TTL; each is checked against a
snapshot or an allowlisted live source. Results are recorded as observations;
the active anchor is never overwritten automatically.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from ..domain.models import Anchor, AnchorObservation
from ..sources.anchor import replay_anchor_result
from ..store import Store
from .anchor_policy import needs_revalidation

AnchorResultFetcher = Callable[[Anchor, str], Awaitable[object | None]]


def due_anchors(
    store: Store, *, now: datetime | None = None, limit: int = 100
) -> list[Anchor]:
    current = now or datetime.now(UTC)
    anchors = store.list_anchors(active_only=True, limit=1000)
    due = [
        anchor
        for anchor in anchors
        if needs_revalidation(anchor, anchor.temporal_sensitivity, now=current)
    ]
    return due[:limit]


async def revalidate_anchor(
    store: Store,
    anchor: Anchor,
    *,
    fetcher: AnchorResultFetcher | None = None,
    now: datetime | None = None,
) -> AnchorObservation:
    current = now or datetime.now(UTC)
    result: object | None
    if fetcher is None:
        result = await replay_anchor_result(store, anchor, current.isoformat())
    else:
        result = await fetcher(anchor, current.isoformat())
    if result is None:
        observation = AnchorObservation(
            id=f"obs_{uuid.uuid4().hex[:10]}",
            anchor_id=anchor.id,
            status="unreachable",
            note="no snapshot/live evidence",
        )
    else:
        observed_hash = str(getattr(result, "content_hash", "") or "")
        changed = bool(
            anchor.content_hash and observed_hash and anchor.content_hash != observed_hash
        )
        observation = AnchorObservation(
            id=f"obs_{uuid.uuid4().hex[:10]}",
            anchor_id=anchor.id,
            status="changed" if changed else "verified",
            content_changed=changed,
            observed_hash=observed_hash,
        )
    store.save_anchor_observation(observation)
    return observation


async def revalidate_due(
    store: Store,
    *,
    fetcher: AnchorResultFetcher | None = None,
    now: datetime | None = None,
    limit: int = 100,
) -> list[AnchorObservation]:
    observations = []
    for anchor in due_anchors(store, now=now, limit=limit):
        observations.append(
            await revalidate_anchor(store, anchor, fetcher=fetcher, now=now)
        )
    return observations

