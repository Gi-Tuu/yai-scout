from __future__ import annotations

from yai_scout.detector.compare import compare_reports
from yai_scout.domain.models import Claim, ClaimType, DetectorReport


def _report(report_id: str, specs: list[tuple[str, ClaimType, list[str]]]) -> DetectorReport:
    claims = [
        Claim(id=f"{report_id}_{index}", text=text, type=claim_type, numbers=numbers)
        for index, (text, claim_type, numbers) in enumerate(specs)
    ]
    return DetectorReport(
        id=report_id,
        answer="a",
        as_of="2026-11-01",
        claims=claims,
        verdicts=[],
    )


def test_compare_does_not_drop_duplicate_identity_keys():
    left = _report(
        "l",
        [
            ("Tavily 500 credits", ClaimType.PRICING, ["500"]),
            ("Tavily 1000 credits", ClaimType.PRICING, ["1000"]),
        ],
    )
    right = _report(
        "r",
        [
            ("Tavily 500 credits", ClaimType.PRICING, ["500"]),
            ("Tavily 2000 credits", ClaimType.PRICING, ["2000"]),
        ],
    )
    drift = compare_reports(left, right)
    assert len(drift.diffs) == 2
    assert {diff.left_claim_id for diff in drift.diffs} == {"l_0", "l_1"}
    assert {diff.right_claim_id for diff in drift.diffs} == {"r_0", "r_1"}
    assert drift.summary["changed"] == 1
    assert drift.summary["stable"] == 1
    assert "Duplicate claim identities" in drift.warning


def test_compare_separates_quarters_and_dates():
    left = _report(
        "l",
        [
            ("Q1 revenue 500", ClaimType.STATISTIC, ["1", "500"]),
            ("deadline 2026-01-01", ClaimType.DATE, ["2026-01-01"]),
        ],
    )
    right = _report(
        "r",
        [
            ("Q2 revenue 500", ClaimType.STATISTIC, ["2", "500"]),
            ("deadline 2027-01-01", ClaimType.DATE, ["2027-01-01"]),
        ],
    )
    drift = compare_reports(left, right)
    assert drift.summary["stable"] == 0
    assert drift.summary["changed"] == 0
    assert drift.summary["new"] == 2
    assert drift.summary["removed"] == 2


def test_compare_matches_rolling_version_but_not_release_specific_facts():
    left = _report(
        "l",
        [
            ("YAI Agent Core 0.24.0", ClaimType.VERSION, ["0.24.0"]),
            ("Python 3.12 was released", ClaimType.VERSION, ["3.12"]),
        ],
    )
    right = _report(
        "r",
        [
            ("YAI Agent Core 0.25.0", ClaimType.VERSION, ["0.25.0"]),
            ("Python 3.13 was released", ClaimType.VERSION, ["3.13"]),
        ],
    )
    drift = compare_reports(left, right)
    assert drift.summary["changed"] == 1
    assert drift.summary["new"] == 1
    assert drift.summary["removed"] == 1
