"""Tests for the private verdict worksheet and human-label evaluation bridge."""
from __future__ import annotations

import json
from pathlib import Path

from yai_scout.detector.verdict_eval import (
    evaluate_labeled_worksheet,
    load_verdict_worksheet,
)

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "benchmarks" / "freshness_verdicts_private.json"
HOLDOUT = ROOT / "benchmarks" / "freshness_verdicts_holdout_v2.json"
HOLDOUT_V3 = ROOT / "benchmarks" / "freshness_verdicts_holdout_v3.json"


def test_private_worksheet_has_no_gold_status() -> None:
    version, cases = load_verdict_worksheet(PRIVATE)
    assert version.startswith("freshness-verdicts-private/")
    assert len(cases) == 30
    assert all(case.expected_status is None for case in cases)
    assert all(case.evidence for case in cases)


def test_labeled_worksheet_evaluation(tmp_path: Path) -> None:
    _, cases = load_verdict_worksheet(PRIVATE)
    labels = {case.id: "insufficient" for case in cases}
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps({
        "version": "freshness-verdict-labels/1.0",
        "labeler": "test",
        "labels": labels,
    }), encoding="utf-8")
    report = evaluate_labeled_worksheet(PRIVATE, labels_path)
    assert report.total == 30
    assert report.matched <= 30
    assert report.status_support["insufficient"] == 30


def test_missing_labels_are_rejected(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.json"
    labels_path.write_text('{"labels":{"PV-001":"fresh"}}', encoding="utf-8")
    try:
        evaluate_labeled_worksheet(PRIVATE, labels_path)
    except ValueError as exc:
        assert "missing labels" in str(exc)
    else:
        raise AssertionError("missing labels should raise")


def test_holdout_v2_is_unlabeled_and_larger() -> None:
    version, cases = load_verdict_worksheet(HOLDOUT)
    assert version == "freshness-verdicts-holdout/2.0"
    assert len(cases) == 60
    assert all(case.expected_status is None for case in cases)


def test_holdout_v3_is_new_and_unlabeled() -> None:
    version, cases = load_verdict_worksheet(HOLDOUT_V3)
    assert version == "freshness-verdicts-holdout/3.0"
    assert len(cases) == 30
    assert all(case.expected_status is None for case in cases)
    assert all(case.id.startswith("HV3-") for case in cases)
