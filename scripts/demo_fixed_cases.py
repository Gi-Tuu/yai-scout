"""Run the fixed demo cases against a Scout instance.

Usage:
    python scripts/demo_fixed_cases.py                 # print cached responses
    python scripts/demo_fixed_cases.py --check         # call API and compare
    python scripts/demo_fixed_cases.py --record        # update cached responses

Cache: benchmarks/demo/responses.json (one response per case id).
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "demo" / "cases.json"
CACHE = ROOT / "benchmarks" / "demo" / "responses.json"


def call(url: str, case: dict) -> dict:
    payload = json.dumps(
        {
            "answer": case["answer"],
            "as_of": case["as_of"],
            "max_claims": 3,
            "mode": case["mode"],
        }
    ).encode()
    request = urllib.request.Request(
        url.rstrip("/") + "/freshness/verify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode())


def statuses(report: dict) -> list[str]:
    return [str(item.get("status")) for item in report.get("verdicts", [])]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    failures = 0

    for case in cases:
        if args.record or args.check:
            report = call(args.url, case)
            if args.record:
                cache[case["id"]] = report
        else:
            report = cache.get(case["id"])
            if report is None:
                print(f"[MISS] {case['id']} no cache; run --record")
                failures += 1
                continue

        found = statuses(report)
        ok = case["expected_status"] in found
        if not ok:
            failures += 1
        print(
            f"[{'OK  ' if ok else 'FAIL'}] {case['id']}: "
            f"expected={case['expected_status']} got={found} "
            f"score={(report.get('verdicts') or [{}])[0].get('score')}"
        )
        if not args.record:
            for verdict in report.get("verdicts", [])[:1]:
                print(f"       {verdict.get('rationale')}")

    if args.record:
        CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"saved {CACHE}")
    print(f"done: failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
