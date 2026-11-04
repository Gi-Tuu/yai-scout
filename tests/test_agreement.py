from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compute_agreement", ROOT / "scripts" / "compute_agreement.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_cohen_kappa_perfect_agreement() -> None:
    a = {"1": "fresh", "2": "stale", "3": "fresh"}
    assert MODULE.cohen_kappa(a, a) == 1.0


def test_cohen_kappa_disagreement() -> None:
    a = {"1": "fresh", "2": "fresh"}
    b = {"1": "stale", "2": "stale"}
    assert MODULE.cohen_kappa(a, b) == 0.0
