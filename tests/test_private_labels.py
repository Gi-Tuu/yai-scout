from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "benchmarks" / "accuracy_gate" / "private_worksheet.json"


def test_private_worksheet_contains_no_answers():
    payload = json.loads(PRIVATE.read_text(encoding="utf-8"))
    assert payload["synthetic_metadata"] is True
    assert len(payload["cases"]) == 30
    assert all("expected" not in case for case in payload["cases"])
    assert all(case["worksheet_id"].startswith("PV-") for case in payload["cases"])
