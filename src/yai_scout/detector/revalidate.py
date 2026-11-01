"""Read-time TTL revalidation for anchors (no in-process scheduler).

Design: due anchors are selected by sensitivity TTL; each is checked against a
snapshot or an allowlisted live source. Results are recorded as observations;
the active anchor is never overwritten automatically.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from ..domain.models import Anchor, AnchorObservation, Claim
from ..retrieval.quality import classify_source
from ..sources.anchor import replay_anchor_result
from ..store import Store
from .anchor_policy import needs_revalidation
from .candidates import (
    create_candidate_from_observations,
    extract_value_hint,
    independent_group_from_url,
)
from .verify import Searcher, build_query

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
        content = str(getattr(result, "content", "") or "")
        changed = bool(
            anchor.content_hash and observed_hash and anchor.content_hash != observed_hash
        )
        observation = AnchorObservation(
            id=f"obs_{uuid.uuid4().hex[:10]}",
            anchor_id=anchor.id,
            status="changed" if changed else "verified",
            content_changed=changed,
            observed_hash=observed_hash,
            url=anchor.url,
            source_tier=anchor.source_tier,
            independent_group=independent_group_from_url(anchor.url),
            value=extract_value_hint(content, anchor.last_value, anchor.claim_text),
            published_at=str(getattr(result, "published_date", "") or "") or None,
        )
    store.save_anchor_observation(observation)
    store.update_anchor(anchor.model_copy(update={"last_checked_at": current.isoformat()}))
    return observation


async def revalidate_due(
    store: Store,
    *,
    fetcher: AnchorResultFetcher | None = None,
    discovery: Searcher | None = None,
    now: datetime | None = None,
    limit: int = 100,
    auto_update: bool = False,
) -> list[AnchorObservation]:
    observations = []
    for anchor in due_anchors(store, now=now, limit=limit):
        observation = await revalidate_anchor(store, anchor, fetcher=fetcher, now=now)
        observations.append(observation)
        if not observation.content_changed or not observation.value:
            continue
        candidates = [observation]
        if discovery is not None:
            claim = Claim(id=anchor.id, text=anchor.claim_text)
            try:
                results, _ = await discovery.search(
                    build_query(claim), max_results=3
                )
            except Exception:  # noqa: BLE001 - discovery failure must not break revalidation
                results = []
            seen = {anchor.url}
            for result in results:
                if result.url in seen:
                    continue
                value = extract_value_hint(result.content, anchor.last_value, anchor.claim_text)
                if not value:
                    continue
                seen.add(result.url)
                tier, _ = classify_source(result.url)
                candidates.append(
                    AnchorObservation(
                        id=f"obs_{uuid.uuid4().hex[:10]}",
                        anchor_id=anchor.id,
                        status="changed",
                        content_changed=True,
                        observed_hash=result.content_hash,
                        url=result.url,
                        source_tier=tier,
                        independent_group=independent_group_from_url(result.url),
                        value=value,
                        published_at=result.published_date,
                    )
                )
        create_candidate_from_observations(
            store, anchor, candidates, auto_update=auto_update
        )
    return observations






