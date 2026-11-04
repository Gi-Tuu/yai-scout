from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "score_external_eval", ROOT / "scripts" / "score_external_eval.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_external_scoring_basic() -> None:
    payload = {
        "method": "synthetic",
        "split": "dev",
        "predictions": [
            {"expected": "stale", "predicted": "stale"},
            {"expected": "stale", "predicted": "fresh"},
            {"expected": "fresh", "predicted": "fresh"},
        ],
    }
    result = MODULE.score(payload)
    assert result["accuracy"] == 2 / 3
    assert result["stale_recall"] == 0.5
    assert result["false_fresh_rate"] == 0.5
    assert result["result_hash"].startswith("sha256:")


def test_external_scoring_bootstrap_is_deterministic() -> None:
    payload = {
        "method": "synthetic",
        "split": "dev",
        "predictions": [
            {"expected": "stale", "predicted": "stale"},
            {"expected": "fresh", "predicted": "fresh"},
        ],
    }
    first = MODULE.score(payload)
    second = MODULE.score(payload)
    assert first["bootstrap_95ci"] == second["bootstrap_95ci"]
