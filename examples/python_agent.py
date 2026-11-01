"""示例 Python Agent：实现 scout-adapter/1.0 的 answer(request) -> response。"""

from __future__ import annotations

from typing import Any

from yai_scout.benchmark.protocol import PROTOCOL_VERSION

ANSWERS = {
    "tavily": (
        "Tavily 免费计划每月 1,000 API credits [1]。",
        ["https://docs.tavily.com/documentation/api-credits"],
    ),
    "bifrost": (
        "Bifrost 使用 Apache-2.0 许可证 [1]。",
        ["https://github.com/maximhq/bifrost"],
    ),
    "yaimodel": (
        "YAI Agent Core 当前版本是 0.25.0 [1]。",
        ["https://github.com/Gi-Tuu/yai-agent-core"],
    ),
}


def answer(request: dict[str, Any]) -> dict[str, Any]:
    question = str(request.get("task", {}).get("question", "")).lower()
    text, citations = "", []
    for key, payload in ANSWERS.items():
        if key in question:
            text, citations = payload
            break
    if not text:
        text = "I cannot verify this from my (offline) knowledge."
    return {
        "protocol_version": PROTOCOL_VERSION,
        "answer": text,
        "citations": citations,
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": "offline-python",
            "provider": "local",
        },
        "cost": {"estimated_usd": 0.0, "price_table_version": "n/a", "estimated": False},
        "latency_ms": 1,
        "trace": [{"step": "offline-lookup"}],
    }

