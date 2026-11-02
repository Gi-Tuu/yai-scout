from __future__ import annotations

import json
from pathlib import Path

from yai_scout.detector.accuracy_gate import (
    GateDecision,
    GateObservation,
    evaluate_gate,
    normalize_value,
)

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "benchmarks" / "accuracy_gate" / "labeled_cases.json"


def _obs(
    value: str,
    *,
    tier: int = 1,
    group: str = "g1",
    published: str | None = "2026-10-01T00:00:00Z",
    reachable: bool = True,
) -> GateObservation:
    return GateObservation(
        url="https://example.com",
        source_tier=tier,
        independent_group=group,
        value=value,
        published_at=published,
        reachable=reachable,
    )


def test_normalization_variants():
    assert normalize_value("1,000")[0] == normalize_value("1000")[0]
    assert normalize_value("1.000")[1] is True
    assert normalize_value("v0.25.0")[0] == normalize_value("0.25.0")[0]
    assert normalize_value("Apache 2.0")[0] == normalize_value("Apache-2.0")[0]
    assert normalize_value("0.30", "$0.30 per M")[0] == normalize_value("$0.30", "$0.30 per M")[0]
    assert normalize_value("$1000")[0] != normalize_value("€1000")[0]
    assert normalize_value("1000 USD")[0] == normalize_value("$1,000")[0]
    assert normalize_value("1000 credits")[0] != normalize_value("$1000")[0]
    assert normalize_value("1000 credits/month")[0] != normalize_value("1000 credits/year")[0]


def test_single_authoritative_source_goes_to_review():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at="2025-01-01T00:00:00Z",
        observations=[_obs("1000")],
    )
    assert result.decision is GateDecision.REVIEW


def test_two_independent_groups_auto_update():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at="2025-01-01T00:00:00Z",
        observations=[_obs("1000", group="docs"), _obs("1,000", tier=2, group="github")],
    )
    assert result.decision is GateDecision.AUTO_UPDATE
    assert result.candidate_value == "num:1000"


def test_older_evidence_is_rejected():
    result = evaluate_gate(
        anchor_value="1000",
        anchor_published_at="2026-09-01T00:00:00Z",
        observations=[_obs("500", published="2025-01-01T00:00:00Z")],
    )
    assert result.decision is GateDecision.REJECT


def test_labeled_cases_match_gate_rules():
    payload = json.loads(LABELS.read_text(encoding="utf-8"))
    from yai_scout.detector.accuracy_gate import evaluate_label_case

    for case in payload["cases"]:
        result = evaluate_label_case(case)
        assert result.decision.value == case["expected"]["decision"], case["id"]


def test_unknown_anchor_time_goes_to_review_not_auto():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at=None,
        observations=[_obs("1000", group="docs"), _obs("1,000", tier=2, group="github")],
    )
    assert result.decision is GateDecision.REVIEW
    assert "anchor publication time" in result.reason


def test_invalid_anchor_time_goes_to_review():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at="not-a-date",
        observations=[_obs("1000", group="docs"), _obs("1,000", tier=2, group="github")],
    )
    assert result.decision is GateDecision.REVIEW


def test_unknown_observation_time_goes_to_review():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at="2025-01-01T00:00:00Z",
        observations=[
            _obs("1000", group="docs", published=None),
            _obs("1,000", tier=2, group="github", published=None),
        ],
    )
    assert result.decision is GateDecision.REVIEW


def test_invalid_observation_time_goes_to_review():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at="2025-01-01T00:00:00Z",
        observations=[
            _obs("1000", group="docs", published="not-a-date"),
            _obs("1,000", tier=2, group="github", published="not-a-date"),
        ],
    )
    assert result.decision is GateDecision.REVIEW


def test_future_observation_time_is_not_current_evidence():
    result = evaluate_gate(
        anchor_value="500",
        anchor_published_at="2025-01-01T00:00:00Z",
        observations=[
            _obs("1000", group="docs", published="2099-01-01T00:00:00Z"),
            _obs("1,000", tier=2, group="github", published="2099-01-01T00:00:00Z"),
        ],
    )
    assert result.decision is GateDecision.REVIEW
