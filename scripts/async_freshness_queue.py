#!/usr/bin/env python3
"""Small async validation queue for freshness demo cases.

Reads JSONL cases, calls /freshness/verify concurrently, and writes one JSONL
result per case. This is a client-side queue for controlled demos; it is not a
persistent server-side job store.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import urllib.error
import urllib.request
from pathlib import Path


def validate(base: str, case: dict) -> dict:
    payload = {
        "answer": case["answer"],
        "as_of": case.get("as_of") or "",
        "max_claims": int(case.get("max_claims") or 3),
        "mode": case.get("mode") or "live",
    }
    request = urllib.request.Request(
        base.rstrip("/") + "/freshness/verify",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            report = json.loads(response.read().decode())
            return {
                "id": case.get("id"),
                "status": (report.get("verdicts") or [{}])[0].get("status", "INSUFFICIENT"),
                "score": report.get("overall_score"),
                "report_id": report.get("id"),
                "report_url": response.headers.get("X-Freshness-Report-URL"),
            }
    except urllib.error.HTTPError as exc:
        return {"id": case.get("id"), "status": "ERROR", "error": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"id": case.get("id"), "status": "ERROR", "error": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", default="results/async_freshness.jsonl")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    cases = [
        json.loads(line)
        for line in Path(args.input).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(validate, args.url, case) for case in cases]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item.get("id")))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"cases": len(results), "statuses": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
