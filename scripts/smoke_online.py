"""在线 Demo 冒烟检查（不消耗 Tavily/LLM 额度，除 --run-benchmark）。

用法：
    python scripts/smoke_online.py --url https://yai-scout.onrender.com
    python scripts/smoke_online.py --url https://xxx.hf.space --run-benchmark
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

CHECKS = [
    ("/api/healthz", "health"),
    ("/", "landing"),
    ("/benchmark", "benchmark page"),
    ("/freshness", "freshness page"),
    ("/inspector", "inspector page"),
    ("/compare", "compare page"),
    ("/api/benchmark/tasks", "dataset"),
]


def get(url: str, timeout: float = 30.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "yai-scout-smoke/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--run-benchmark", action="store_true")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    failures = 0
    for path, label in CHECKS:
        status, body = get(base + path)
        ok = status == 200
        failures += 0 if ok else 1
        print(f"[{'OK ' if ok else 'FAIL'}] {label:<16} {path:<24} HTTP {status}")
        if path == "/api/healthz" and ok:
            try:
                data = json.loads(body)
                print(
                    f"       mode={data.get('mode')} tavily={data.get('tavily', {}).get('mode')} "
                    f"llm={data.get('llm', {}).get('available')} snapshots={data.get('snapshots')}"
                )
            except json.JSONDecodeError:
                pass

    if args.run_benchmark:
        payload = json.dumps(
            {"agent_ids": ["mock_good", "mock_stale"], "task_ids": ["b_tavily_free_credits"]}
        ).encode()
        req = urllib.request.Request(
            base + "/benchmark/runs",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                session = json.loads(resp.read().decode())["session"]
            print(f"[OK ] benchmark run created {session['id']}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] benchmark run: {type(exc).__name__}: {exc}")

    print(f"done: failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
