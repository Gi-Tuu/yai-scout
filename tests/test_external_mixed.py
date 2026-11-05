from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "benchmarks" / "external_v2"


def test_mixed_manifest_is_smoke() -> None:
    manifest = json.loads((V2 / "mixed_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "mechanical_mixed_smoke"
    assert manifest["independent_labels"] is False
    assert manifest["cases"] == 9
    assert set(manifest["status_counts"]) == {
        "conflicted",
        "insufficient",
        "unknown",
    }


def test_mixed_summary_has_no_predictions() -> None:
    summary = json.loads(
        (V2 / "results" / "mixed_summary.json").read_text(encoding="utf-8")
    )
    assert summary["independent_labels"] is False
    assert summary["status"] == "mechanical_mixed_smoke"
    assert "yais_full" in summary["methods"]
    assert "predictions" not in summary["methods"]["yais_full"]
