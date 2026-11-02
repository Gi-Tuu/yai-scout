# ruff: noqa: E501
"""Check a private label file for coverage and obvious inconsistencies.

Usage:
    python scripts/check_label_quality.py \
      --worksheet benchmarks/accuracy_gate/private_worksheet.json \
      --labels accuracy_labels_private_<name>.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from yai_scout.detector.accuracy_gate import normalize_value

DECISIONS = {"auto_update", "review", "reject", "no_change"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worksheet", required=True)
    parser.add_argument("--labels", required=True)
    args = parser.parse_args()

    cases = json.loads(Path(args.worksheet).read_text(encoding="utf-8"))["cases"]
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8")).get("labels", {})
    distribution = Counter(labels.values())
    missing = [case["worksheet_id"] for case in cases if case["worksheet_id"] not in labels]
    invalid = [key for key, value in labels.items() if value not in DECISIONS]
    suspicious: list[str] = []
    for case in cases:
        key = case["worksheet_id"]
        if labels.get(key) != "no_change":
            continue
        claim = str(case.get("claim_text") or "")
        anchor, _ = normalize_value(str(case["anchor"].get("value") or ""), claim)
        observed = [
            normalize_value(str(item.get("value") or ""), claim)[0]
            for item in case.get("observations", [])
            if item.get("reachable", True) and item.get("value")
        ]
        if observed and anchor not in observed:
            suspicious.append(key)

    print(f"labeler={json.loads(Path(args.labels).read_text(encoding='utf-8')).get('labeler', 'unknown')}")
    print(f"coverage={len(labels)}/{len(cases)} missing={len(missing)}")
    print(f"distribution={dict(distribution)}")
    if invalid:
        print(f"INVALID_DECISIONS={invalid}")
    if missing:
        print(f"MISSING_IDS={missing}")
    if suspicious:
        print(f"SUSPICIOUS_NO_CHANGE={suspicious}")
    ok = not missing and not invalid and not suspicious
    print(f"quality={'ok' if ok else 'needs_review'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

