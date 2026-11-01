"""Make a blind labeling worksheet + hidden key from the 60 labeled cases.

Usage:
    python scripts/make_labeling_worksheet.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "benchmarks" / "accuracy_gate" / "labeled_cases.json"
OUT = ROOT / "benchmarks" / "accuracy_gate" / "holdout_worksheet.json"
KEY = ROOT / "benchmarks" / "accuracy_gate" / "holdout_key.json"
WEB = ROOT / "web" / "static"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    cases = list(data["cases"])
    random.Random(20261101).shuffle(cases)

    worksheet = []
    key: dict[str, dict[str, str]] = {}
    for index, case in enumerate(cases, start=1):
        wid = f"BL-{index:03d}"
        worksheet.append(
            {
                "worksheet_id": wid,
                "claim_text": case["claim_text"],
                "claim_key": case["claim_key"],
                "temporal_sensitivity": case["temporal_sensitivity"],
                "anchor": case["anchor"],
                "observations": case["observations"],
            }
        )
        key[wid] = {
            "source_id": case["id"],
            "expected_decision": case["expected"]["decision"],
            "expected_reason": case["expected"].get("reason", ""),
        }

    payload = {
        "version": "accuracy-gate-worksheet/0.1",
        "instructions": (
            "Blind labeling: do not open holdout_key.json. "
            "Choose auto_update / review / reject / no_change per case."
        ),
        "cases": worksheet,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    KEY.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "accuracy_worksheet.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"worksheet={len(worksheet)} key={len(key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

