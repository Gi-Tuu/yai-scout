from yai_scout.detector.claims import classify, extract_claims, extract_numbers
from yai_scout.domain.models import ClaimType


def test_extract_numbers_normalizes():
    assert extract_numbers("价格 $0.30 / 1,000 credits") == ["0.30", "1000"]


def test_classify_types():
    assert classify("The plan costs $20 per month.")[0] is ClaimType.PRICING
    assert classify("Version 2.4.1 was released.")[0] is ClaimType.VERSION
    assert classify("The CEO resigned yesterday.")[0] is ClaimType.LEADERSHIP
    assert classify("This is a sentence without signals.")[0] is ClaimType.OTHER


def test_extract_claims_keeps_time_sensitive_sentences():
    answer = (
        "Tavily 免费计划每月提供 1000 credits。"
        "今天天气不错，适合出门散步。"
        "YAI Agent Core 当前版本是 0.25.0。"
    )
    claims = extract_claims(answer)
    assert len(claims) >= 2
    texts = " ".join(c.text for c in claims)
    assert "1000 credits" in texts
    assert "0.25.0" in texts
    assert all(c.type is not ClaimType.OTHER for c in claims)
    assert all(c.id for c in claims)
