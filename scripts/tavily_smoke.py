"""Tavily 冒烟测试：验证 key 可用并查看 credits 消耗。

用法：
    python scripts/tavily_smoke.py --query "your query"
    python scripts/tavily_smoke.py --query "..." --depth advanced --max-results 3

说明：
- 优先读环境变量 TAVILY_API_KEY；缺失时尝试读项目根目录 .env（不打印值）。
- 只输出标题/URL/credits，绝不打印 key。
- 仅用标准库，便于在未装依赖的环境里先跑通。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.tavily.com/search"
ROOT = Path(__file__).resolve().parents[1]


def load_key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == "TAVILY_API_KEY":
                return value.strip().strip('"').strip("'")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Tavily smoke test")
    parser.add_argument("--query", required=True)
    parser.add_argument("--depth", default="basic", choices=["basic", "advanced"])
    parser.add_argument("--max-results", type=int, default=3)
    args = parser.parse_args()

    key = load_key()
    if not key:
        print("ERROR: TAVILY_API_KEY 未找到（环境变量或 .env）。", file=sys.stderr)
        return 2

    payload = json.dumps(
        {
            "query": args.query,
            "search_depth": args.depth,
            "max_results": args.max_results,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本只需可读错误
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    results = body.get("results") or []
    credits = (body.get("usage") or {}).get("credits")
    print(f"results={len(results)} credits={credits} response_time={body.get('response_time')}")
    for item in results[: args.max_results]:
        print(f"- {item.get('title', '')[:90]}")
        print(f"  {item.get('url', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
