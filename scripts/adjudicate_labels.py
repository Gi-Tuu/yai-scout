"""Compare two independent label files and emit disagreements for adjudication.

Usage:
    python scripts/adjudicate_labels.py \
      --a labels_a.json --b labels_b.json --out disagreements.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    parser.add_argument("--out", default="adjudication_disagreements.json")
    args = parser.parse_args()

    a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    labels_a = a.get("labels", {})
    labels_b = b.get("labels", {})
    common = sorted(set(labels_a) & set(labels_b))
    disagreements = [
        {"worksheet_id": key, "a": labels_a[key], "b": labels_b[key]}
        for key in common
        if labels_a[key] != labels_b[key]
    ]
    agreement = (len(common) - len(disagreements)) / len(common) if common else 0.0
    result = {
        "labeler_a": a.get("labeler", "unknown"),
        "labeler_b": b.get("labeler", "unknown"),
        "overlap": len(common),
        "agreement": round(agreement, 4),
        "disagreements": disagreements,
    }
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"overlap={len(common)} agreement={agreement:.3f} "
        f"disagreements={len(disagreements)} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
