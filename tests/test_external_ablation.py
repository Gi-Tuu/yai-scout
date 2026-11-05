from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_per_status_counts() -> None:
    score = _load("score_external_eval")
    rows = [
        {"source_family": "a", "claim_type": "version"},
        {"source_family": "a", "claim_type": "version"},
        {"source_family": "b", "claim_type": "pricing"},
    ]
    result = score.metrics(
        ["stale", "fresh", "stale"],
        ["stale", "fresh", "fresh"],
        [
            {**row, "expected": e, "predicted": p}
            for row, e, p in zip(
                rows, ["stale", "fresh", "stale"], ["stale", "fresh", "fresh"],
                strict=True,
            )
        ],
    )
    assert result["accuracy"] == 2 / 3
    status = score.per_status(
        ["stale", "fresh", "stale"], ["stale", "fresh", "fresh"]
    )
    assert status["stale"]["support"] == 2
    assert status["stale"]["recall"] == 0.5


def test_mcnemar_counts() -> None:
    compare = _load("compare_external_eval")
    full = [
        {"expected": "stale", "predicted": "stale"},
        {"expected": "fresh", "predicted": "fresh"},
    ]
    base = [
        {"expected": "stale", "predicted": "fresh"},
        {"expected": "fresh", "predicted": "fresh"},
    ]
    result = compare._mcnemar(full, base)
    assert result["full_only"] == 1
    assert result["baseline_only"] == 0
    assert result["p_value"] == 1.0


def test_ablation_summary_is_mechanical() -> None:
    import json

    summary = json.loads(
        (ROOT / "benchmarks" / "external_v2" / "results" / "ablation_summary.json")
        .read_text(encoding="utf-8")
    )
    assert summary["label_status"] == "mechanical_holdout"
    assert summary["independent_labels"] is False
    assert any(item["variant"] == "full" for item in summary["variants"])
