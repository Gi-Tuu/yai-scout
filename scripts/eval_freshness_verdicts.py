#!/usr/bin/env python
"""Evaluate claim-level Freshness verdicts against gold cases or human labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from yai_scout.detector.verdict_eval import (
    evaluate_labeled_worksheet,
    evaluate_verdict_cases,
    load_verdict_cases,
    render_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate deterministic freshness verdicts.")
    parser.add_argument("--cases", default=None, help="gold verdict case JSON")
    parser.add_argument("--worksheet", default=None, help="unlabeled verdict worksheet")
    parser.add_argument("--labels", default=None, help="human labels JSON for --worksheet")
    parser.add_argument("--as-of", default=None, help="override as_of date")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args(argv)

    if args.worksheet:
        if not args.labels:
            parser.error("--worksheet requires --labels")
        report = evaluate_labeled_worksheet(
            args.worksheet, args.labels, as_of=args.as_of,
        )
    else:
        version, cases = load_verdict_cases(args.cases)
        payload_path = Path(args.cases) if args.cases else Path(
            "benchmarks/freshness_verdicts.json"
        )
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        report = evaluate_verdict_cases(
            cases,
            as_of=args.as_of or payload.get("as_of") or "2026-11-01",
            dataset_version=version,
        )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(report))
    return 0 if report.accuracy >= args.min_accuracy else 1


if __name__ == "__main__":
    raise SystemExit(main())
