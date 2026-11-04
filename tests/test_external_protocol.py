from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "benchmarks" / "external_v1"


def test_protocol_primary_is_citation_only() -> None:
    protocol = json.loads((EXTERNAL / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["primary"]["baseline"] == "citation_only"
    assert "llm_only" not in protocol["primary"]


def test_test_manifest_is_mechanical_not_independent() -> None:
    manifest = json.loads((EXTERNAL / "test_manifest.json").read_text(encoding="utf-8"))
    assert manifest["independent_labels"] is False
    assert manifest["labelers"] == []
    assert manifest["kappa"] is None
    assert manifest["test_results"] is None


def test_no_committed_test_results() -> None:
    results = EXTERNAL / "results"
    assert not list(results.glob("test_*.json"))


def test_results_docs_use_primary_citation_only() -> None:
    text = (ROOT / "docs" / "external-benchmark-results.md").read_text(encoding="utf-8")
    primary = text.split("## Primary comparison", 1)[1].split("## Secondary", 1)[0]
    assert "citation_only" in primary
    assert "pre-registered +0.10 advantage over LLM-only" not in text
    assert "threshold_met = true" in primary


def test_dev_summary_matches_protocol() -> None:
    summary = json.loads(
        (EXTERNAL / "results" / "dev_summary.json").read_text(encoding="utf-8")
    )
    assert summary["primary"]["baseline"] == "citation_only"
    assert summary["primary"]["threshold_met"] is True
    assert summary["protocol_hash"].startswith("sha256:")
