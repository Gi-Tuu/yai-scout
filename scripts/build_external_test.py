"""Build the mechanically-labelled holdout candidate.

The test claim/evidence files are public. Gold labels are written to an ignored
`mechanical_holdout/` directory. These labels are not independent human labels
and must not be described as a blind external test.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_external_set import build

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "external_v1"
PACKAGES = [
    "pandas", "scikit-learn", "flask", "sqlalchemy", "pydantic", "boto3",
    "scipy", "matplotlib", "celery", "tornado", "click", "httpx",
]
DEV_FAMILIES = {
    "pypi:fastapi", "pypi:requests", "pypi:django", "pypi:numpy", "pypi:pytest",
}


def main() -> int:
    snapshots = OUT / "snapshots"
    cases = build(PACKAGES, 8, snapshots)
    cases = [case for case in cases if case["source_family"] not in DEV_FAMILIES]
    if len(cases) < 120:
        raise SystemExit(f"only {len(cases)} test candidates; need >=120")
    test_rows = []
    label_rows = []
    for case in cases:
        public = {
            key: value
            for key, value in case.items()
            if key not in {"gold_status", "gold_current_value", "gold_support"}
        }
        public["split"] = "test"
        test_rows.append(public)
        label_rows.append({
            "id": case["id"],
            "gold_status": case["gold_status"],
            "gold_current_value": case["gold_current_value"],
            "gold_support": case["gold_support"],
        })
    test_path = OUT / "test.jsonl"
    test_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in test_rows) + "\n",
        encoding="utf-8",
    )
    holdout = OUT / "mechanical_holdout"
    holdout.mkdir(parents=True, exist_ok=True)
    labels_path = holdout / "labels_test.jsonl"
    labels_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in label_rows) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "version": "external-v1",
        "split": "test",
        "cases": len(test_rows),
        "source_families": sorted({row["source_family"] for row in test_rows}),
        "test_hash": hashlib.sha256(test_path.read_bytes()).hexdigest(),
        "labels_hash": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        "labels_location": "mechanical_holdout/labels_test.jsonl (git-ignored)",
        "labels_status": "mechanical_holdout",
        "independent_labels": False,
        "labelers": [],
        "kappa": None,
        "test_results": None,
    }
    (OUT / "test_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"test_cases={len(test_rows)} labels={labels_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
