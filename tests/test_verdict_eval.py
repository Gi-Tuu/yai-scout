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
    assert version == "freshness-verdicts/1.1"
    assert len(cases) == 50
    report = evaluate_verdict_cases(cases, as_of="2026-11-01")
    assert report.accuracy == 1.0
    assert report.matched == report.total == 50
    assert report.status_support["fresh"] == 19
    assert report.status_support["stale"] == 10
    assert report.status_support["conflicted"] == 8
    assert report.status_support["insufficient"] == 13
    assert report.scored_cases == 39


def test_evaluator_detects_a_wrong_label() -> None:
    _, cases = load_verdict_cases()
    mutated = list(cases)
    case = cases[0]
    mutated[0] = case.model_copy(update={"expected_status": FreshnessStatus.STALE})
    report = evaluate_verdict_cases(mutated, as_of="2026-11-01")
    assert report.matched == 49
    assert report.accuracy == round(49 / 50, 4)
    assert report.confusion["stale"]["fresh"] == 1
    assert "mismatches:" in render_text(report)


def test_evaluator_reports_abstention() -> None:
    _, cases = load_verdict_cases()
    report = evaluate_verdict_cases(cases, as_of="2026-11-01")
    assert report.abstention_rate == round(13 / 50, 4)
    assert report.status_predicted["insufficient"] == 13


def test_case_type_metrics() -> None:
    _, cases = load_verdict_cases()
    report = evaluate_verdict_cases(cases, as_of="2026-11-01")
    assert report.case_type_support["standard"] == 46
    assert report.case_type_support["adversarial"] == 3
    assert report.case_type_support["ambiguous"] == 1
    assert report.case_type_accuracy["adversarial"] == 1.0
    assert report.case_type_accuracy["ambiguous"] == 1.0
