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


def metrics(expected: list[str], predicted: list[str]) -> dict[str, float]:
    stale = [i for i, value in enumerate(expected) if value == "stale"]
    stale_hit = sum(1 for i in stale if predicted[i] == "stale")
    stable = [i for i, value in enumerate(expected) if value == "fresh"]
    false_stale = sum(1 for i in stable if predicted[i] == "stale")
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
        "stale_cases": float(len(stale)),
        "fresh_cases": float(len(stable)),
    }


def bootstrap(
    expected: list[str], predicted: list[str], *, rounds: int = 2000, seed: int = 7
) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {"accuracy": [], "stale_recall": []}
    for _ in range(rounds):
        indices = [rng.randrange(len(expected)) for _ in expected]
        e = [expected[i] for i in indices]
        p = [predicted[i] for i in indices]
        result = metrics(e, p)
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
    result = metrics(expected, predicted)
    result["bootstrap_95ci"] = {
        key: list(value) for key, value in bootstrap(expected, predicted).items()
    }
    result["confusion"] = {
        f"{gold}->{pred}": count
        for (gold, pred), count in Counter(zip(expected, predicted, strict=False)).items()
    }
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
