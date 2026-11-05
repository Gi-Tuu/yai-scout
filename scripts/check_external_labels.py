"""Validate independent labeler files and compute Cohen's kappa."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

STATUSES = {"fresh", "stale", "conflicted", "insufficient", "unknown"}
REQUIRED = {"id", "status"}


def _read(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        if not set(row) >= REQUIRED:
            raise ValueError(f"{path}: missing id/status")
        if row["status"] not in STATUSES:
            raise ValueError(f"{path}: invalid status {row['status']}")
        if row["id"] in result:
            raise ValueError(f"{path}: duplicate id {row['id']}")
        result[row["id"]] = row["status"]
    return result


def kappa(a: dict[str, str], b: dict[str, str]) -> float:
    ids = sorted(set(a) & set(b))
    if not ids:
        raise ValueError("no shared ids")
    total = len(ids)
    labels = sorted(set(a.values()) | set(b.values()))
    observed = sum(a[i] == b[i] for i in ids) / total
    expected = sum(
        (sum(a[i] == label for i in ids) / total)
        * (sum(b[i] == label for i in ids) / total)
        for label in labels
    )
    return 1.0 if expected == 1.0 else (observed - expected) / (1.0 - expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    parser.add_argument("--adjudicated", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    a = _read(Path(args.a))
    b = _read(Path(args.b))
    shared = set(a) & set(b)
    if not shared:
        raise SystemExit("no shared ids")
    if args.adjudicated:
        adj = _read(Path(args.adjudicated))
        missing = shared - set(adj)
        if missing:
            raise SystemExit(f"adjudicated missing {len(missing)} ids")
    value = kappa(a, b)
    output = {
        "ids": len(shared),
        "kappa": round(value, 4),
        "kappa_min": 0.7,
        "passes_kappa": value >= 0.7,
        "agreements": sum(a[i] == b[i] for i in shared),
        "disagreements": sum(a[i] != b[i] for i in shared),
    }
    text = json.dumps(output, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
