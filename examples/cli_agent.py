#!/usr/bin/env python
"""示例 CLI Agent：stdin 读 scout-adapter 请求 JSON，stdout 写响应 JSON。"""

from __future__ import annotations

import json
import sys

from yai_scout.benchmark.protocol import PROTOCOL_VERSION

ANSWERS = {
    "tavily": ("Tavily 免费计划每月 1,000 API credits [1]。", ["https://docs.tavily.com/documentation/api-credits"]),
    "bifrost": ("Bifrost 使用 Apache-2.0 许可证 [1]。", ["https://github.com/maximhq/bifrost"]),
    "yaimodel": ("YAI Agent Core 当前版本是 0.25.0 [1]。", ["https://github.com/Gi-Tuu/yai-agent-core"]),
}


def main() -> int:
    request = json.loads(sys.stdin.read() or "{}")
    question = str(request.get("task", {}).get("question", "")).lower()
    text, citations = "", []
    for key, payload in ANSWERS.items():
        if key in question:
            text, citations = payload
            break
    if not text:
        text = "I cannot verify this from my (offline) knowledge."
    print(
        json.dumps(
            {
                "protocol_version": PROTOCOL_VERSION,
                "answer": text,
                "citations": citations,
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "model": "offline-cli",
                    "provider": "local",
                },
                "cost": {"estimated_usd": 0.0, "price_table_version": "n/a", "estimated": False},
                "latency_ms": 1,
                "trace": [{"step": "offline-lookup"}],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
