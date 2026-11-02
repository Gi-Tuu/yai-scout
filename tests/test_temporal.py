from __future__ import annotations

from yai_scout.detector.temporal import classify_temporal
from yai_scout.domain.models import Claim, ClaimType, TemporalSensitivity


def _date_claim(text: str) -> Claim:
    return Claim(id="c", text=text, type=ClaimType.DATE, numbers=[])


def test_past_year_is_stable():
    sensitivity, _, _ = classify_temporal(
        _date_claim("Python 3.12 于 1998 年发布"), target_time="2026-11-01"
    )
    assert sensitivity is TemporalSensitivity.STABLE


def test_current_and_future_years_are_not_stable():
    for year in ("2026", "2099"):
        sensitivity, _, _ = classify_temporal(
            _date_claim(f"Python 3.12 于 {year} 年发布"),
            target_time="2026-11-01",
        )
        assert sensitivity is not TemporalSensitivity.STABLE
