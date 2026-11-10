from __future__ import annotations

from yai_scout.detector.temporal import (
    apply_temporal_classification,
    classify_temporal,
)
from yai_scout.domain.models import Claim, ClaimType, TemporalSensitivity


def _claim(text: str, claim_type: ClaimType = ClaimType.OTHER) -> Claim:
    return Claim(id="c", text=text, type=claim_type, numbers=[])


def test_volatile_and_math_signals() -> None:
    volatile, window, reasons = classify_temporal(_claim("当前股价排名第一"))
    assert volatile is TemporalSensitivity.VOLATILE
    assert window == 30 and reasons
    stable, _, _ = classify_temporal(_claim("1 英里等于多少公里", ClaimType.STATISTIC))
    assert stable is TemporalSensitivity.STABLE


def test_type_branches() -> None:
    pricing, _, _ = classify_temporal(_claim("价格是 10 美元", ClaimType.PRICING))
    assert pricing is TemporalSensitivity.SENSITIVE
    law, _, _ = classify_temporal(_claim("该法规最新版本", ClaimType.LAW))
    assert law is TemporalSensitivity.SENSITIVE
    slow_law, _, _ = classify_temporal(_claim("某法规框架", ClaimType.LAW))
    assert slow_law is TemporalSensitivity.SLOW
    leadership, _, _ = classify_temporal(_claim("CEO 是某人", ClaimType.LEADERSHIP))
    assert leadership is TemporalSensitivity.SLOW
    fallback, _, _ = classify_temporal(_claim("其他事实"))
    assert fallback is TemporalSensitivity.SENSITIVE


def test_apply_returns_target_and_window() -> None:
    claim = apply_temporal_classification(
        _claim("1 GB 等于多少 MB", ClaimType.STATISTIC),
        target_time="2026-11-01",
    )
    assert claim.target_time == "2026-11-01"
    assert claim.temporal_sensitivity is TemporalSensitivity.STABLE
    assert claim.validity_window_days == 3650
