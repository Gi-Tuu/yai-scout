#!/usr/bin/env python
"""Small deterministic P50/P95/P99 smoke benchmark for the freshness scorer."""
from __future__ import annotations

import argparse
import json
import statistics
import time

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.detector.verdict_eval import load_verdict_cases
from yai_scout.domain.models import Claim


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")

    _, cases = load_verdict_cases()
    samples: list[float] = []
    for _ in range(args.iterations):
        for case in cases:
            claim = Claim(
                id=case.id,
                text=case.claim.text,
                type=case.claim.type,
                temporal_sensitivity=case.claim.temporal_sensitivity,
                target_time=case.claim.target_time or "2026-11-01",
            )
            started = time.perf_counter_ns()
            score_claim(
                claim,
                case.evidence,
                as_of=as_of_datetime(claim.target_time or "2026-11-01"),
            )
            samples.append((time.perf_counter_ns() - started) / 1_000_000)

    result = {
        "cases": len(cases),
        "iterations": args.iterations,
        "samples": len(samples),
        "p50_ms": round(_percentile(samples, 0.50), 4),
        "p95_ms": round(_percentile(samples, 0.95), 4),
        "p99_ms": round(_percentile(samples, 0.99), 4),
        "mean_ms": round(statistics.fmean(samples), 4),
        "max_ms": round(max(samples), 4),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
