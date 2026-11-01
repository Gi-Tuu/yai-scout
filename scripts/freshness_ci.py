"""Freshness CI: fail a build when an answer/document contains stale claims.

Usage:
    python scripts/freshness_ci.py README.md
    python scripts/freshness_ci.py answer.txt --fail-on stale,conflicted
    python scripts/freshness_ci.py - --url https://yai-scout.onrender.com --as-of 2026-11-01

Exit codes: 0 = no failing status; 1 = stale/conflicted (or configured failure); 2 = request error.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_FAIL_ON = "stale,conflicted"


def verify(
    url: str, text: str, *, as_of: str | None, mode: str, max_claims: int
) -> dict:
    payload = json.dumps(
        {
            "answer": text,
            "as_of": as_of,
            "max_claims": max_claims,
            "mode": mode,
        }
    ).encode()
    request = urllib.request.Request(
        url.rstrip("/") + "/freshness/verify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        return json.loads(response.read().decode())


def decide(verdicts: list[dict], fail_on: set[str]) -> list[dict]:
    return [
        verdict
        for verdict in verdicts
        if str(verdict.get("status", "")).lower() in fail_on
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="-")
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--mode", choices=["live", "replay"], default="live")
    parser.add_argument("--max-claims", type=int, default=6)
    parser.add_argument("--fail-on", default=DEFAULT_FAIL_ON)
    args = parser.parse_args()

    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    if not text.strip():
        print("empty input")
        return 2

    fail_on = {item.strip().lower() for item in args.fail_on.split(",") if item.strip()}
    try:
        report = verify(
            args.url,
            text,
            as_of=args.as_of,
            mode=args.mode,
            max_claims=args.max_claims,
        )
    except urllib.error.HTTPError as exc:
        print(f"request failed: HTTP {exc.code} {exc.read().decode()[:300]}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"request failed: {type(exc).__name__}: {exc}")
        return 2

    verdicts = report.get("verdicts", [])
    claims = {claim["id"]: claim for claim in report.get("claims", [])}
    print(f"mode={report.get('mode')} as_of={report.get('as_of')} claims={len(verdicts)}")
    for verdict in verdicts:
        claim = claims.get(verdict.get("claim_id"), {})
        print(
            f"  [{verdict.get('status')}] score={verdict.get('score')} "
            f"{claim.get('text', '')[:90]}"
        )
    failing = decide(verdicts, fail_on)
    if failing:
        print(f"FAIL: {len(failing)} claim(s) matched fail-on={sorted(fail_on)}")
        return 1
    print("PASS: no failing claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
