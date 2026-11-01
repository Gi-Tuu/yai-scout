"""Anchor selection and revalidation policy (deterministic, read-time TTL)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..domain.models import Anchor, TemporalSensitivity

TTL_DAYS: dict[TemporalSensitivity, int] = {
    TemporalSensitivity.STABLE: 365,
    TemporalSensitivity.SLOW: 90,
    TemporalSensitivity.SENSITIVE: 7,
    TemporalSensitivity.VOLATILE: 1,
}


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def select_anchors(anchors: list[Anchor], *, limit: int = 2) -> list[Anchor]:
    """Deterministic authority ordering: tier asc, then newest published/verified."""
    ordered = sorted(
        anchors,
        key=lambda item: (
            item.source_tier,
            -(_parse(item.published_at) or datetime.min.replace(tzinfo=UTC)).timestamp(),
            -(
                _parse(item.last_verified_at) or datetime.min.replace(tzinfo=UTC)
            ).timestamp(),
            item.id,
        ),
    )
    return ordered[:limit]


def needs_revalidation(
    anchor: Anchor,
    sensitivity: TemporalSensitivity | None,
    *,
    now: datetime | None = None,
) -> bool:
    if sensitivity is None:
        return True
    ttl = TTL_DAYS.get(sensitivity, 7)
    verified = _parse(anchor.last_verified_at)
    checked = _parse(anchor.last_checked_at)
    reference = max(
        [value for value in (verified, checked) if value is not None],
        default=None,
    )
    if reference is None:
        return True
    current = now or datetime.now(UTC)
    return current - reference > timedelta(days=ttl)

