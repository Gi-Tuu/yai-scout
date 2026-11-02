from __future__ import annotations

from yai_scout.detector.compare import claim_key


def test_claim_key_groups_same_fact_with_changed_value():
    assert claim_key("Tavily 免费 500 credits") == claim_key("Tavily 免费 1,000 credits")
    assert claim_key("Python 3.12 发布") == claim_key("Python 3.13 发布")


def test_claim_key_keeps_distinct_entities_apart():
    assert claim_key("Tavily 免费 500 credits") != claim_key("Bifrost 免费 500 credits")


def test_claim_key_known_period_collision_is_documented():
    # Known limitation: period numbers are treated as values. Kept for
    # backward compatibility with existing anchor keys.
    assert claim_key("第1季度营收 500") == claim_key("第2季度营收 600")
