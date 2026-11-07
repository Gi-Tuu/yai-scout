#!/usr/bin/env python3
"""Six showcase cases for the freshness demo.

Usage:
  python scripts/demo_showcase_cases.py --check https://yai-scout.onrender.com
"""
from __future__ import annotations

import argparse
import json
import urllib.request

CASES = [
    {
        "id": "stable_release",
        "label": "stable / historical fact",
        "answer": "Python 3.12 于 2023 年发布。",
        "as_of": "2026-11-01",
        "mode": "live",
    },
    {
        "id": "pricing_current",
        "label": "pricing / current",
        "answer": "Tavily 免费计划每月提供 1000 credits。",
        "as_of": "2026-11-01",
        "mode": "live",
    },
    {
        "id": "version_stale",
        "label": "version / stale",
        "answer": "YAI Agent Core 当前版本是 0.24.0。",
        "as_of": "2026-11-01",
        "mode": "replay",
    },
    {
        "id": "leadership",
        "label": "company / leadership",
        "answer": "Apple 的 CEO 是 Tim Cook。",
        "as_of": "2026-11-01",
        "mode": "live",
    },
    {
        "id": "regulation",
        "label": "regulation / stable",
        "answer": "GDPR 于 2018 年 5 月 25 日生效。",
        "as_of": "2026-11-01",
        "mode": "live",
    },
    {
        "id": "insufficient",
        "label": "no usable evidence",
        "answer": "Acme 公司 2030 年的营收会达到 1000 亿美元。",
        "as_of": "2026-11-01",
        "mode": "live",
    },
]


def check(base: str, case: dict) -> dict:
    body = json.dumps(
        {
            "answer": case["answer"],
            "as_of": case["as_of"],
            "max_claims": 3,
            "mode": case["mode"],
        }
    ).encode()
    request = urllib.request.Request(
        base.rstrip("/") + "/freshness/verify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        report = json.loads(response.read().decode())
        headers = {
            key: response.headers.get(key)
            for key in (
                "X-Freshness-Status",
                "X-Freshness-Score",
                "X-Freshness-Report-URL",
            )
        }
    verdicts = report.get("verdicts") or []
    return {
        "id": case["id"],
        "label": case["label"],
        "status": verdicts[0]["status"] if verdicts else "INSUFFICIENT",
        "score": report.get("overall_score"),
        "claims": len(report.get("claims") or []),
        "headers": headers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", help="base URL of a running YAI Scout")
    args = parser.parse_args()
    if not args.check:
        for case in CASES:
            print(f"{case['id']:20} {case['label']:24} {case['mode']}")
        return 0
    for case in CASES:
        result = check(args.check, case)
        print(
            f"{result['id']:20} {result['status']:14} "
            f"score={result['score']} claims={result['claims']} "
            f"url={result['headers'].get('X-Freshness-Report-URL')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
