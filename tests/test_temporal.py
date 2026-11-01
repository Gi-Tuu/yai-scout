from yai_scout.detector.temporal import classify_temporal
from yai_scout.domain.models import Claim, ClaimType, TemporalSensitivity


def claim(text: str, claim_type: ClaimType = ClaimType.OTHER) -> Claim:
    return Claim(id="c1", text=text, type=claim_type)


def test_pricing_is_sensitive():
    sensitivity, window, reasons = classify_temporal(
        claim("Tavily 免费计划每月 1,000 credits", ClaimType.PRICING),
        target_time="2026-11-01",
    )
    assert sensitivity is TemporalSensitivity.SENSITIVE
    assert window == 180
    assert reasons


def test_past_date_is_stable():
    sensitivity, window, _ = classify_temporal(
        claim("Python 3.12 于 2023 年发布", ClaimType.DATE), target_time="2026-11-01"
    )
    assert sensitivity is TemporalSensitivity.STABLE
    assert window == 3650


def test_volatile_ranking():
    sensitivity, window, _ = classify_temporal(
        claim("当前 AI 芯片厂商排名第一的是 NVIDIA", ClaimType.STATISTIC),
        target_time="2026-11-01",
    )
    assert sensitivity is TemporalSensitivity.VOLATILE
    assert window == 30


def test_law_is_slow_unless_current():
    slow, _, _ = classify_temporal(
        claim("某法规框架适用于 AI 系统", ClaimType.LAW), target_time="2026-11-01"
    )
    assert slow is TemporalSensitivity.SLOW
    sensitive, _, _ = classify_temporal(
        claim("欧盟 AI Act 最新生效条款适用范围", ClaimType.LAW),
        target_time="2026-11-01",
    )
    assert sensitive is TemporalSensitivity.SENSITIVE


def test_past_release_is_stable_even_if_version_type():
    sensitivity, _, _ = classify_temporal(
        claim("Python 3.12 于 2023 年发布", ClaimType.VERSION), target_time="2026-11-01"
    )
    assert sensitivity is TemporalSensitivity.STABLE


def test_math_is_stable():
    sensitivity, _, _ = classify_temporal(
        claim("1 英里等于多少公里", ClaimType.STATISTIC), target_time="2026-11-01"
    )
    assert sensitivity is TemporalSensitivity.STABLE
