"""Benchmark 评分：数字/字符串匹配 + 综合分。"""

from __future__ import annotations

import re

from ..domain.models import TaskResult

NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")


def normalize(text: str) -> str:
    return (
        text.lower()
        .replace(",", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("¥", "")
        .replace(" ", "")
    )


def match_gold(gold: str, answer: str) -> bool:
    g = normalize(gold)
    normalized_answer = normalize(answer)
    if not g:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", g):
        target = float(g)
        for token in NUMBER_TOKEN.findall(normalized_answer):
            try:
                if abs(float(token) - target) < 1e-9:
                    return True
            except ValueError:
                continue
        return False
    return g in normalized_answer


def numeric_accuracy(gold_values: list[str], answer: str) -> float:
    if not gold_values:
        return 0.0
    hits = sum(1 for gold in gold_values if match_gold(gold, answer))
    return round(hits / len(gold_values), 3)


def composite_score(
    *,
    numeric: float,
    has_citations: bool,
    stale_rate: float | None,
    completed: bool,
    cost_usd: float,
) -> float:
    citation = 1.0 if has_citations else 0.0
    freshness = 1.0 - (stale_rate or 0.0)
    cost_component = 1.0 / (1.0 + max(cost_usd, 0.0) * 20.0)
    score = (
        0.45 * numeric
        + 0.20 * citation
        + 0.15 * freshness
        + 0.10 * (1.0 if completed else 0.0)
        + 0.10 * cost_component
    )
    return round(score, 4)


def leaderboard(results: list[TaskResult]) -> list[dict[str, float | str]]:
    """按 agent 聚合：均分、数字准确率、陈旧率、引用率、时延。"""
    grouped: dict[str, list[TaskResult]] = {}
    for result in results:
        grouped.setdefault(result.agent_id, []).append(result)
    rows: list[dict[str, float | str]] = []
    for agent_id, items in grouped.items():
        count = len(items)
        rows.append(
            {
                "agent_id": agent_id,
                "runs": count,
                "score": round(sum(i.score for i in items) / count, 4),
                "numeric_accuracy": round(sum(i.numeric_accuracy for i in items) / count, 3),
                "citation_rate": round(sum(1 for i in items if i.has_citations) / count, 3),
                "stale_rate": round(
                    sum(i.stale_claim_rate or 0.0 for i in items) / count, 3
                ),
                "freshness_score": round(
                    sum(i.freshness_score or 0 for i in items) / count, 1
                ),
                "avg_latency_s": round(sum(i.answer.latency_s for i in items) / count, 2),
                "avg_tokens": round(sum(i.answer.tokens for i in items) / count, 0),
                "errors": sum(1 for i in items if i.error or i.answer.error),
            }
        )
    rows.sort(key=lambda row: (-float(row["score"]), str(row["agent_id"])))
    return rows
