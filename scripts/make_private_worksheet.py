# ruff: noqa: E501
"""Generate the private accuracy worksheet (cases only, no answer key).

The worksheet is safe to publish: it contains claims/sources but **no expected
decisions**. The labels come from an independent annotator and stay private.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "accuracy_gate"
WEB = ROOT / "web" / "static"


def case(
    index: int,
    claim: str,
    sensitivity: str,
    anchor_value: str,
    observations: list[tuple[str, int, str, str, str | None, bool]],
) -> dict:
    return {
        "worksheet_id": f"PV-{index:03d}",
        "claim_text": claim,
        "temporal_sensitivity": sensitivity,
        "anchor": {
            "url": "https://docs.example.com/source",
            "source_tier": 1,
            "value": anchor_value,
            "published_at": "2025-01-01T00:00:00Z",
            "content_hash": f"old-{index:03d}",
        },
        "observations": [
            {
                "url": url,
                "source_tier": tier,
                "independent_group": group,
                "value": value,
                "published_at": published,
                "content_hash": f"new-{index:03d}-{position}",
                "reachable": reachable,
            }
            for position, (url, tier, group, value, published, reachable) in enumerate(
                observations
            )
        ],
    }


D1 = "2026-10-01T00:00:00Z"
D2 = "2026-10-02T00:00:00Z"
D_OLD = "2024-01-01T00:00:00Z"

cases = [
    case(1, "Tavily 学生计划每月提供 4,000 credits", "sensitive", "1000", [
        ("https://help.tavily.com/student", 1, "tavily-help", "4000", D1, True),
        ("https://docs.tavily.com/student", 1, "tavily-docs", "4,000", D2, True),
    ]),
    case(2, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "500", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "1000", D1, True),
        ("https://github.com/tavily-ai/tavily-python", 2, "tavily-github", "1,000", D2, True),
    ]),
    case(3, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "500", [
        ("https://some-blog.example/tavily", 3, "some-blog", "1000", D1, True),
    ]),
    case(4, "Tavily basic extract 每 5 个 URL 消耗 1 credit", "sensitive", "2", [
        ("https://docs.tavily.com/extract", 1, "tavily-docs", "1", D1, True),
        ("https://github.com/tavily-ai/tavily-python", 2, "tavily-github", "1", D2, True),
    ]),
    case(5, "Tavily advanced search 每次 2 credits", "sensitive", "1", [
        ("https://docs.tavily.com/search", 1, "tavily-docs", "2", D1, True),
    ]),
    case(6, "DeepSeek V4.1-Flash 输入 $0.30 / 百万 token", "sensitive", "0.20", [
        ("https://api-docs.deepseek.com/pricing", 1, "deepseek-docs", "$0.30", D1, True),
        ("https://platform.deepseek.com/pricing", 1, "deepseek-platform", "0.30", D2, True),
    ]),
    case(7, "DeepSeek V4.1-Flash 输入 $0.30 / 百万 token", "sensitive", "0.20", [
        ("https://api-docs.deepseek.com/pricing", 1, "deepseek-docs", "€0.30", D1, True),
        ("https://platform.deepseek.com/pricing", 1, "deepseek-platform", "$0.30", D2, True),
    ]),
    case(8, "Claude Haiku 5.5 输出 $0.50 / 百万 token", "sensitive", "0.80", [
        ("https://platform.claude.com/pricing", 1, "anthropic-docs", "$0.50", D1, True),
        ("https://docs.anthropic.com/pricing", 2, "anthropic-docs-v2", "0.50", D2, True),
    ]),
    case(9, "Bifrost 使用 Apache-2.0 许可证", "slow", "AGPL-3.0", [
        ("https://github.com/maximhq/bifrost", 1, "bifrost-github", "Apache-2.0", D1, True),
        ("https://docs.getbifrost.ai/overview", 1, "bifrost-docs", "Apache 2.0", D2, True),
    ]),
    case(10, "Bifrost 默认监听 8080 端口", "sensitive", "8000", [
        ("https://docs.getbifrost.ai/overview", 1, "bifrost-docs", "8080", D1, True),
        ("https://github.com/maximhq/bifrost", 2, "bifrost-github", "8080", D2, True),
    ]),
    case(11, "YAI Agent Core 当前版本是 0.25.0", "sensitive", "0.24.0", [
        ("https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0", 2, "github-yai", "v0.25.0", D1, True),
        ("https://pypi.org/project/yai-agent-core/", 1, "pypi", "0.25.0", D2, True),
    ]),
    case(12, "Python 3.13 于 2024 年发布", "stable", "2023", [
        ("https://docs.python.org/3.13/whatsnew", 1, "python-docs", "2024", D1, True),
        ("https://en.wikipedia.org/wiki/CPython", 2, "wikipedia", "2024", D2, True),
    ]),
    case(13, "HTTP 404 表示 Not Found", "stable", "410 Gone", [
        ("https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404", 1, "mdn", "Not Found", D1, True),
        ("https://en.wikipedia.org/wiki/List_of_HTTP_status_codes", 2, "wikipedia", "Not Found", D2, True),
    ]),
    case(14, "Python 3.13 于 2024 年 10 月发布", "sensitive", "2026-11-22", [
        ("https://docs.python.org/3.13/whatsnew/3.13.html", 1, "python-docs", "2026-11-15", D1, True),
    ]),
    case(15, "Tavily 学生计划每月提供 4,000 credits", "sensitive", "1000", [
        ("https://some-blog.example/tavily-student", 3, "some-blog", "4000", D1, True),
    ]),
    case(16, "DeepSeek V4.1-Flash 输入 $0.30 / 百万 token", "sensitive", "0.20", [
        ("https://api-docs.deepseek.com/pricing", 1, "deepseek-docs", "0.30", D1, True),
    ]),
    case(17, "Bifrost 默认监听 8080 端口", "sensitive", "8000", [
        ("https://docs.getbifrost.ai/overview", 1, "bifrost-docs", "8080", D1, True),
        ("https://github.com/maximhq/bifrost", 2, "bifrost-github", "8000", D2, True),
    ]),
    case(18, "YAI Agent Core 当前版本是 0.25.0", "sensitive", "0.25.0", [
        ("https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0", 2, "github-yai", "0.24.0", D_OLD, True),
    ]),
    case(19, "Bifrost 使用 MIT 许可证", "slow", "Apache-2.0", [
        ("https://github.com/maximhq/bifrost", 1, "bifrost-github", "MIT", D1, True),
    ]),
    case(20, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "1000", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "500", D_OLD, True),
    ]),
    case(21, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "1000", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "$1000", D1, True),
    ]),
    case(22, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "1000 credits/month", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "1000 credits/year", D1, True),
    ]),
    case(23, "YAI Agent Core 当前版本是 0.25", "sensitive", "0.25.0", [
        ("https://github.com/Gi-Tuu/yai-agent-core/releases", 2, "github-yai", "0.25", D1, True),
    ]),
    case(24, "Python 3.13 于 2024 年 10 月发布", "sensitive", "2026-11-15T23:59:00+05:30", [
        ("https://docs.python.org/3.13/whatsnew/3.13.html", 1, "python-docs", "2026-11-15", D1, True),
        ("https://www.tavily.com/community", 2, "tavily-community", "2026-11-15", D2, True),
    ]),
    case(25, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "500", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "1000", D1, True),
        ("https://cdn.docs.tavily.com/credits", 1, "tavily-docs", "1000", D2, True),
    ]),
    case(26, "Bifrost 默认监听 8080 端口", "sensitive", "8000", [
        ("https://docs.getbifrost.ai/overview", 1, "bifrost-docs", "", D1, False),
    ]),
    case(27, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "500", [
        ("https://some-blog.example/tavily", 4, "some-blog", "1000", D1, True),
    ]),
    case(28, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "500", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "1000", D1, True),
        ("https://docs.tavily.com/credits-v2", 1, "tavily-docs", "500", D2, True),
    ]),
    case(29, "Tavily 免费计划每月提供 1,000 credits", "sensitive", "1000", [
        ("https://docs.tavily.com/credits", 1, "tavily-docs", "1,000", D1, True),
    ]),
    case(30, "Bifrost 默认监听 8080 端口", "sensitive", "8000", [
        ("https://docs.getbifrost.ai/overview", 1, "bifrost-docs", "8080", D1, True),
        ("https://github.com/maximhq/bifrost", 2, "bifrost-github", "8080", D2, True),
        ("https://some-blog.example/bifrost", 3, "some-blog", "8000", D1, True),
    ]),
]

payload = {
    "version": "accuracy-gate-private-worksheet/0.1",
    "synthetic_metadata": True,
    "instructions": "Independent labels only; holdout decisions are not in this file.",
    "cases": cases,
}
text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
BENCH.mkdir(parents=True, exist_ok=True)
WEB.mkdir(parents=True, exist_ok=True)
(BENCH / "private_worksheet.json").write_text(text, encoding="utf-8")
(WEB / "private_worksheet.json").write_text(text, encoding="utf-8")
print(f"private worksheet cases={len(cases)} (no answer key)")

