"""Trigger due-anchor revalidation via the admin endpoint.

Designed for an external scheduler (GitHub Actions / cron-job.org), not an
in-process daemon.

Usage:
    SCOUT_ADMIN_TOKEN=... python scripts/revalidate_anchors.py --url https://...
    SCOUT_ADMIN_TOKEN=... python scripts/revalidate_anchors.py --fail-on-changed

Exit codes: 0 = ok; 2 = request failed or changed with --fail-on-changed.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("SCOUT_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--fail-on-changed", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("SCOUT_ADMIN_TOKEN", "")
    if not token:
        print("SCOUT_ADMIN_TOKEN is not set")
        return 2

    payload = json.dumps({"limit": args.limit}).encode()
    request = urllib.request.Request(
        args.url.rstrip("/") + "/admin/anchors/revalidate",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()[:300]}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"request failed: {type(exc).__name__}: {exc}")
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_on_changed and result.get("changed", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
