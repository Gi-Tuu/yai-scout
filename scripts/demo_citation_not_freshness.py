"""Demo: a perfectly cited answer that is still stale.

Runs the same answer against two as-of dates using the replay snapshot store:
- 2026-10-28: v0.24.0 was the latest release → FRESH
- 2026-11-01: v0.25.0 superseded it → STALE

Usage:
    python scripts/demo_citation_not_freshness.py
    python scripts/demo_citation_not_freshness.py --url https://yai-scout.onrender.com
"""

from __future__ import annotations

import argparse
import json
import urllib.request

ANSWER = (
    "YAI Agent Core 当前版本是 0.24.0。"
    "来源：https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0"
)
DATES = ("2026-10-28", "2026-11-01")


def call(url: str, as_of: str) -> dict:
    payload = json.dumps(
        {"answer": ANSWER, "as_of": as_of, "max_claims": 2, "mode": "replay"}
    ).encode()
    request = urllib.request.Request(
        url.rstrip("/") + "/freshness/verify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    args = parser.parse_args()

    print(f"ANSWER: {ANSWER}\n")
    for as_of in DATES:
        report = call(args.url, as_of)
        verdict = (report.get("verdicts") or [{}])[0]
        print(f"as_of={as_of}")
        print(
            f"  status={verdict.get('status')} score={verdict.get('score')} "
            f"mode={report.get('mode')}"
        )
        print(f"  rationale={verdict.get('rationale')}")
        for evidence in (verdict.get("evidence") or [])[:2]:
            print(
                f"  evidence: {evidence.get('relation')} "
                f"{evidence.get('published_at')} {evidence.get('url')}"
            )
        print()
    print("Point: the citation is real and supports the claim, but the claim is no longer current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
