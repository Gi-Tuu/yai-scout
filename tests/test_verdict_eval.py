"""Contract tests for the claim-level Freshness verdict evaluator."""
from __future__ import annotations

from yai_scout.detector.verdict_eval import (
    evaluate_verdict_cases,
    load_verdict_cases,
    render_text,
)
from yai_scout.domain.models import FreshnessStatus


def test_verdict_fixtures_are_gold_consistent() -> None:
    version, cases = load_verdict_cases()
    assert version == "freshness-verdicts/1.0"
    assert len(cases) == 14
    report = evaluate_verdict_cases(cases, as_of="2026-11-01")
    assert report.accuracy == 1.0
    assert report.matched == report.total == 14
    assert report.status_support["fresh"] == 5
    assert report.status_support["stale"] == 2
    assert report.status_support["conflicted"] == 2
    assert report.status_support["insufficient"] == 5
    assert report.scored_cases == 10


def test_evaluator_detects_a_wrong_label() -> None:
    _, cases = load_verdict_cases()
    mutated = list(cases)
    case = cases[0]
    mutated[0] = case.model_copy(update={"expected_status": FreshnessStatus.STALE})
    report = evaluate_verdict_cases(mutated, as_of="2026-11-01")
    assert report.matched == 13
    assert report.accuracy == round(13 / 14, 4)
    assert report.confusion["stale"]["fresh"] == 1
    assert "mismatches:" in render_text(report)


def test_evaluator_reports_abstention() -> None:
    _, cases = load_verdict_cases()
    report = evaluate_verdict_cases(cases, as_of="2026-11-01")
    assert report.abstention_rate == round(5 / 14, 4)
    assert report.status_predicted["insufficient"] == 5
