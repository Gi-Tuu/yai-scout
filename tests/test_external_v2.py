from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "benchmarks" / "external_v2"
SPEC = importlib.util.spec_from_file_location(
    "check_external_labels", ROOT / "scripts" / "check_external_labels.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_v2_protocol_is_mechanical_holdout() -> None:
    protocol = json.loads((EXTERNAL / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["primary"]["baseline"] == "citation_only"
    assert protocol["test_status"]["independent_labels"] is False
    assert protocol["test_status"]["label_status"] == "mechanical_holdout"
    assert protocol["test_status"]["kappa"] is None


def test_v2_summary_is_aggregate_only() -> None:
    summary = json.loads(
        (EXTERNAL / "results" / "test_summary.json").read_text(encoding="utf-8")
    )
    assert summary["label_status"] == "mechanical_holdout"
    assert summary["independent_labels"] is False
    assert summary["primary"]["baseline"] == "citation_only"
    assert summary["primary"]["threshold_met"] is True
    assert "predictions" not in summary


def test_label_checker_accepts_agreement_files(tmp_path: Path) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(
        '{"id":"1","status":"fresh"}\n{"id":"2","status":"stale"}\n',
        encoding="utf-8",
    )
    b.write_text(
        '{"id":"1","status":"fresh"}\n{"id":"2","status":"stale"}\n',
        encoding="utf-8",
    )
    assert MODULE.kappa(MODULE._read(a), MODULE._read(b)) == 1.0
