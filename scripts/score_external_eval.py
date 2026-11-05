"""Score external-eval predictions with macro-F1 and bootstrap intervals."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

STATUSES = ("fresh", "stale", "conflicted", "insufficient", "unknown")


def _f1(expected: list[str], predicted: list[str], label: str) -> float:
    tp = sum(1 for e, p in zip(expected, predicted, strict=False) if e == p == label)
    fp = sum(1 for e, p in zip(expected, predicted, strict=False) if e != label and p == label)
    fn = sum(1 for e, p in zip(expected, predicted, strict=False) if e == label and p != label)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def per_status(
    expected: list[str], predicted: list[str]
) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for label in sorted(set(expected)):
        tp = sum(1 for e, p in zip(expected, predicted, strict=False) if e == p == label)
        fp = sum(
            1 for e, p in zip(expected, predicted, strict=False)
            if e != label and p == label
        )
        fn = sum(
            1 for e, p in zip(expected, predicted, strict=False)
            if e == label and p != label
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        result[label] = {
            "support": sum(1 for value in expected if value == label),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(
                2 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0,
                4,
            ),
        }
    return result


def per_group(payload_rows: list[dict], key: str) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict]] = {}
    for row in payload_rows:
        name = str(row.get(key) or "unknown")
        groups.setdefault(name, []).append(row)
    result: dict[str, dict[str, float]] = {}
    for name, rows in sorted(groups.items()):
        expected = [str(row["expected"]) for row in rows]
        predicted = [str(row["predicted"]) for row in rows]
        result[name] = {
            "cases": float(len(rows)),
            "accuracy": round(
                sum(e == p for e, p in zip(expected, predicted, strict=False))
                / len(rows),
                4,
            ),
            "macro_f1": round(
                sum(_f1(expected, predicted, label) for label in sorted(set(expected)))
                / len(set(expected)),
                4,
            ),
        }
    return result


def metrics(
    expected: list[str], predicted: list[str], payload_rows: list[dict]
) -> dict[str, float]:
    stale = [i for i, value in enumerate(expected) if value == "stale"]
    stale_hit = sum(1 for i in stale if predicted[i] == "stale")
    stable = [i for i, value in enumerate(expected) if value == "fresh"]
    false_stale = sum(1 for i in stable if predicted[i] == "stale")
    value_rows = [
        row
        for row in payload_rows
        if row["expected"] == "stale" and row.get("current_value") is not None
    ]
    value_hits = sum(
        1
        for row in value_rows
        if row.get("current_value") == row.get("gold_current_value")
    )
    return {
        "accuracy": sum(e == p for e, p in zip(expected, predicted, strict=False)) / len(expected),
        "macro_f1": sum(
            _f1(expected, predicted, label) for label in sorted(set(expected))
        ) / len(set(expected)),
        "stale_recall": stale_hit / len(stale) if stale else 0.0,
        "false_fresh_rate": (
            sum(1 for i in stale if predicted[i] == "fresh") / len(stale)
            if stale else 0.0
        ),
        "stable_false_stale": false_stale / len(stable) if stable else 0.0,
        "abstention_rate": sum(
            value in {"insufficient", "unknown"} for value in predicted
        ) / len(predicted),
        "current_value_accuracy": value_hits / len(value_rows) if value_rows else 0.0,
        "current_value_cases": float(len(value_rows)),
        "stale_cases": float(len(stale)),
        "fresh_cases": float(len(stable)),
    }


def bootstrap(
    expected: list[str],
    predicted: list[str],
    payload_rows: list[dict],
    *,
    rounds: int = 2000,
    seed: int = 7,
) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {"accuracy": [], "stale_recall": []}
    for _ in range(rounds):
        indices = [rng.randrange(len(expected)) for _ in expected]
        e = [expected[i] for i in indices]
        p = [predicted[i] for i in indices]
        result = metrics(e, p, [payload_rows[i] for i in indices])
        samples["accuracy"].append(result["accuracy"])
        samples["stale_recall"].append(result["stale_recall"])
    result: dict[str, tuple[float, float]] = {}
    for key, values in samples.items():
        values.sort()
        result[key] = (values[int(0.025 * rounds)], values[int(0.975 * rounds) - 1])
    return result


def score(payload: dict) -> dict:
    expected = [row["expected"] for row in payload["predictions"]]
    predicted = [row["predicted"] for row in payload["predictions"]]
    result = metrics(expected, predicted, payload["predictions"])
    result["bootstrap_95ci"] = {
        key: list(value)
        for key, value in bootstrap(
            expected, predicted, payload["predictions"]
        ).items()
    }
    result["confusion"] = {
        f"{gold}->{pred}": count
        for (gold, pred), count in Counter(zip(expected, predicted, strict=False)).items()
    }
    result["per_status"] = per_status(expected, predicted)
    result["per_source_family"] = per_group(payload["predictions"], "source_family")
    result["per_claim_type"] = per_group(payload["predictions"], "claim_type")
    result["cases"] = len(expected)
    result["method"] = payload["method"]
    result["split"] = payload["split"]
    canonical = json.dumps(result, sort_keys=True, ensure_ascii=False)
    result["result_hash"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    result = score(json.loads(Path(args.input).read_text(encoding="utf-8")))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
