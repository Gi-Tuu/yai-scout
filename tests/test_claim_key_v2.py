from __future__ import annotations

from yai_scout.detector.compare import claim_key, claim_key_v2, claim_keys


def test_v1_is_unchanged_for_compatibility():
    assert claim_key("第1季度营收 500") == claim_key("第2季度营收 600")


def test_v2_keeps_periods_and_dates_distinct():
    assert claim_key_v2("第1季度营收 500") != claim_key_v2("第2季度营收 600")
    assert claim_key_v2("2026 年截止") != claim_key_v2("2027 年截止")
    assert claim_key_v2("2026-01-01 发布") != claim_key_v2("2026-02-01 发布")


def test_v2_normalizes_values_but_keeps_units():
    assert claim_key_v2("Tavily 500 credits") == claim_key_v2("Tavily 1,000 credits")
    assert claim_key_v2("Tavily 500 credits") != claim_key_v2("Tavily 500 USD")


def test_v2_version_token_depends_on_claim_type():
    assert claim_key_v2("当前版本 0.24.0", "version") == claim_key_v2(
        "当前版本 0.25.0", "version"
    )
    assert claim_key_v2("Python 3.12 supported") != claim_key_v2(
        "Python 3.13 supported"
    )
    assert claim_key_v2("Python 3.12 发布") == claim_key_v2("Python 3.13 发布")


def test_claim_keys_returns_both():
    v1, v2 = claim_keys("Tavily 500 credits")
    assert v1 == claim_key("Tavily 500 credits")
    assert v2 == claim_key_v2("Tavily 500 credits")
