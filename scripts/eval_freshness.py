"""评估 Freshness 判定与评分（20 条人工标注 claim）。

用法：
    python scripts/eval_freshness.py
    python scripts/eval_freshness.py --calibrate

说明：标签只标 expected status（不标人类分数）；MAE 使用"由状态推导的目标分"
（fresh 85 / stale 25 / conflicted 50 / insufficient 30），仅用于比较权重，不是真值。
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from yai_scout.detector.freshness import DEFAULT_WEIGHTS, score_claim
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    TemporalSensitivity,
)

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "benchmarks" / "labeled_claims.json"
TARGET = datetime(2026, 11, 1, tzinfo=UTC)
STATUS_TARGET = {
    "fresh": 85.0,
    "stale": 25.0,
    "conflicted": 50.0,
    "insufficient": 30.0,
}


def build_case(item: dict) -> tuple[Claim, list[EvidenceRef], str]:
    claim = Claim(
        id=item["id"],
        text=item["text"],
        type=ClaimType(item["type"]),
        target_time="2026-11-01",
        temporal_sensitivity=TemporalSensitivity(item["sensitivity"]),
        validity_window_days=180,
    )
    evidence = []
    for ev in item.get("evidence", []):
        published = TARGET - timedelta(days=int(ev["days_ago"]))
        evidence.append(
            EvidenceRef(
                url="https://example.com",
                published_at=published.isoformat(),
                tier=int(ev["tier"]),
                relation=ev["relation"],
            )
        )
    return claim, evidence, item["expected"]


def evaluate(weights: dict[str, float] | None = None) -> tuple[float, float, list[dict]]:
    payload = json.loads(LABELS.read_text(encoding="utf-8"))
    correct = 0
    errors: list[float] = []
    details: list[dict] = []
    for item in payload["claims"]:
        claim, evidence, expected = build_case(item)
        verdict = score_claim(claim, evidence, as_of=TARGET, weights=weights)
        ok = verdict.status.value == expected
        correct += 1 if ok else 0
        if verdict.score is not None and expected in STATUS_TARGET:
            errors.append(abs(verdict.score - STATUS_TARGET[expected]))
        details.append(
            {
                "id": item["id"],
                "expected": expected,
                "actual": verdict.status.value,
                "score": verdict.score,
                "ok": ok,
            }
        )
    accuracy = correct / len(details)
    mae = sum(errors) / len(errors) if errors else 0.0
    return accuracy, mae, details


def calibrate() -> None:
    best: list[tuple[float, float, dict[str, float]]] = []
    for relation in [round(x * 0.1, 1) for x in range(3, 8)]:
        for recency in [round(x * 0.1, 1) for x in range(1, 5)]:
            authority = round(1.0 - relation - recency, 1)
            if authority < 0.1:
                continue
            weights = {"relation": relation, "recency": recency, "authority": authority}
            accuracy, mae, _ = evaluate(weights)
            best.append((accuracy, -mae, weights))
    best.sort(reverse=True)
    print("top weights (accuracy, -MAE, weights):")
    for accuracy, neg_mae, weights in best[:5]:
        print(f"  acc={accuracy:.3f} mae={-neg_mae:.2f} {weights}")
    print(f"default: {DEFAULT_WEIGHTS}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()

    accuracy, mae, details = evaluate()
    print(f"status_accuracy={accuracy:.3f} score_mae={mae:.2f} (n={len(details)})")
    for row in details:
        if not row["ok"]:
            print(
                f"  MISS {row['id']}: expected={row['expected']} actual={row['actual']}"
                f" score={row['score']}"
            )
    if args.calibrate:
        calibrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
