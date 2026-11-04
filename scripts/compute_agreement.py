"""Compute Cohen's kappa for two independent annotation files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        result[row["id"]] = row["status"]
    return result


def cohen_kappa(a: dict[str, str], b: dict[str, str]) -> float:
    ids = sorted(set(a) & set(b))
    if not ids:
        raise ValueError("no shared ids")
    labels = sorted({a[i] for i in ids} | {b[i] for i in ids})
    total = len(ids)
    observed = sum(a[i] == b[i] for i in ids) / total
    expected = sum(
        (sum(a[i] == label for i in ids) / total)
        * (sum(b[i] == label for i in ids) / total)
        for label in labels
    )
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    args = parser.parse_args(argv)
    a, b = _read(Path(args.a)), _read(Path(args.b))
    ids = set(a) & set(b)
    kappa = cohen_kappa(a, b)
    print(json.dumps({
        "ids": len(ids),
        "kappa": round(kappa, 4),
        "agreements": sum(a[i] == b[i] for i in ids),
        "disagreements": sum(a[i] != b[i] for i in ids),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
