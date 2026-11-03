from __future__ import annotations

import random
import string

from yai_scout.claim_keys import claim_key, claim_key_v2, claim_keys


def test_v2_amount_changes_are_stable_property():
    rng = random.Random(20261103)
    for _ in range(300):
        value_a = rng.randint(0, 10_000)
        value_b = rng.randint(0, 10_000)
        text_a = f"Tavily 免费 {value_a:,} credits"
        text_b = f"Tavily 免费 {value_b:,} credits"
        assert claim_key_v2(text_a, "pricing") == claim_key_v2(text_b, "pricing")


def test_v2_quarters_are_distinct_property():
    for quarter in ("Q1", "Q2", "Q3", "Q4"):
        for other in ("Q1", "Q2", "Q3", "Q4"):
            if quarter == other:
                continue
            assert claim_key_v2(f"{quarter} revenue 500", "statistic") != claim_key_v2(
                f"{other} revenue 500", "statistic"
            )


def test_v2_preserves_dates_property():
    for date in ("2026-01-01", "2026-11-03", "1998-12-31"):
        key = claim_key_v2(f"deadline {date}", "date")
        assert date in key


def test_v2_is_deterministic_for_random_unicode_inputs():
    rng = random.Random(42)
    alphabet = string.ascii_letters + string.digits + " 年月日季度%$€£¥版本发布"
    for _ in range(500):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 60)))
        assert claim_key_v2(text, "other") == claim_key_v2(text, "other")
        assert claim_key(text) == claim_key(text)
        v1, v2 = claim_keys(text, "other")
        assert isinstance(v1, str) and isinstance(v2, str)


def test_v2_does_not_raise_on_empty_or_weird_values():
    for text in ("", " ", "\n\t", "0", "0%" * 100, "2026-13-99", "版本" * 100):
        assert isinstance(claim_key_v2(text, "other"), str)
