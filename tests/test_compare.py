from yai_scout.detector.compare import claim_key, compare_reports
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    DetectorReport,
    EvidenceRef,
    FreshnessStatus,
    FreshnessVerdict,
    TemporalSensitivity,
)


def _report(
    report_id: str, as_of: str, claims: list[tuple[str, list[str], str, int]]
) -> DetectorReport:
    claim_models = []
    verdicts = []
    for index, (text, numbers, status, score) in enumerate(claims):
        claim = Claim(
            id=f"{report_id}_c{index}",
            text=text,
            type=ClaimType.PRICING,
            numbers=numbers,
            temporal_sensitivity=TemporalSensitivity.SENSITIVE,
        )
        claim_models.append(claim)
        verdicts.append(
            FreshnessVerdict(
                claim_id=claim.id,
                status=FreshnessStatus(status),
                score=score,
                confidence=0.8,
                evidence=[
                    EvidenceRef(
                        url=f"https://example.com/{as_of}/{index}",
                        relation="supports",
                        tier=2,
                    )
                ],
            )
        )
    return DetectorReport(
        id=report_id,
        answer="answer",
        as_of=as_of,
        claims=claim_models,
        verdicts=verdicts,
        overall_score=float(sum(v.score or 0 for v in verdicts)) / max(1, len(verdicts)),
    )


def test_claim_key_normalizes_numbers():
    assert claim_key("Tavily 免费 500 credits") == claim_key("Tavily 免费 1,000 credits")


def test_compare_detects_changed_and_new_removed():
    left = _report(
        "left",
        "2025-06-01",
        [
            ("Tavily 免费 500 credits", ["500"], "stale", 30),
            ("Bifrost 是 gateway", [], "fresh", 80),
        ],
    )
    right = _report(
        "right",
        "2026-11-01",
        [
            ("Tavily 免费 1,000 credits", ["1000"], "fresh", 90),
            ("YAI 版本 0.25.0", ["0.25.0"], "fresh", 85),
        ],
    )
    drift = compare_reports(left, right)
    assert drift.mode == "simulated"
    assert drift.warning
    changes = {diff.change for diff in drift.diffs}
    assert {"changed", "new", "removed"} <= changes
    changed = next(diff for diff in drift.diffs if diff.change == "changed")
    assert changed.numbers_left == ["500"]
    assert changed.numbers_right == ["1000"]
    assert changed.freshness_delta == 60


def test_compare_same_as_of_is_live_mode():
    report = _report("a", "2026-11-01", [("x 1", ["1"], "fresh", 80)])
    drift = compare_reports(report, report)
    assert drift.mode == "live"
    assert drift.summary["stable"] == 1

