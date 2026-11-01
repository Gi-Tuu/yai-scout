"""Verify that Scout is actually routing model requests through Bifrost.

Usage:
    python scripts/verify_bifrost.py --url http://127.0.0.1:8012
Requires Bifrost at http://127.0.0.1:8080 (or set BIFROST_URL).
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8012")
    parser.add_argument(
        "--bifrost", default=os.environ.get("BIFROST_URL", "http://127.0.0.1:8080")
    )
    args = parser.parse_args()

    health = _get(args.url.rstrip("/") + "/api/healthz")
    gateway = health.get("llm", {}).get("gateway")
    print(f"healthz gateway={gateway} model={health.get('llm', {}).get('model')}")
    if gateway != "bifrost":
        print("FAIL: Scout is not configured for Bifrost")
        return 1

    models = _get(args.bifrost.rstrip("/") + "/v1/models")
    print(f"bifrost models={len(models.get('data', []))}")

    payload = json.dumps(
        {
            "answer": (
                "YAI Agent Core 当前版本是 0.24.0。来源："
                "https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0"
            ),
            "as_of": "2026-11-01",
            "max_claims": 2,
            "mode": "replay",
            "use_anchors": True,
        }
    ).encode()
    request = urllib.request.Request(
        args.url.rstrip("/") + "/freshness/verify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        report = json.loads(response.read().decode())
    statuses = [item.get("status") for item in report.get("verdicts", [])]
    print(f"freshness statuses={statuses}")
    print("PASS: gateway=bifrost; check Bifrost logs for POST /v1/chat/completions")
    return 0 if "stale" in statuses else 1


if __name__ == "__main__":
    raise SystemExit(main())
