"""Benchmark 评分：数字/字符串匹配 + 综合分。"""

from __future__ import annotations

import re

from ..domain.models import (
    BenchmarkTask,
    DetectorReport,
    FreshnessStatus,
    TaskResult,
    TemporalSensitivity,
)

NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")
TIER_WEIGHTS = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.25}


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


def expected_accuracy(task: BenchmarkTask, answer: str) -> float:
    """按 expected_claims 逐条匹配（金标为 alternatives，命中任一即可）。"""
    if not task.expected_claims:
        return numeric_accuracy(task.gold_values, answer)
    hits = 0
    for expected in task.expected_claims:
        if expected.gold_values:
            if any(match_gold(gold, answer) for gold in expected.gold_values):
                hits += 1
        elif normalize(expected.text)[:24] in normalize(answer):
            hits += 1
    return round(hits / len(task.expected_claims), 3)


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


def claim_coverage(task: BenchmarkTask, answer: str) -> float:
    """金标 expected_claims 在答案中的覆盖比例。"""
    if not task.expected_claims:
        return 0.0
    normalized_answer = normalize(answer)
    hits = 0
    for expected in task.expected_claims:
        if expected.gold_values and any(
            match_gold(gold, answer) for gold in expected.gold_values
        ) or normalize(expected.text)[:24] in normalized_answer:
            hits += 1
    return round(hits / len(task.expected_claims), 3)


def evidence_metrics(report: DetectorReport | None) -> dict[str, float | None]:
    """从 Freshness 报告提取证据质量 / 支持率 / 稳定事实完整性 / 权威度。"""
    if report is None or not report.claims:
        return {
            "evidence_quality": None,
            "supported_claim_rate": None,
            "stable_fact_integrity": None,
            "authority": None,
        }
    verdicts = report.verdicts
    with_evidence = [
        v
        for v in verdicts
        if v.evidence and any(e.relation in {"supports", "contradicts"} for e in v.evidence)
    ]
    supported = [
        v for v in verdicts if any(e.relation == "supports" for e in v.evidence)
    ]
    tiers = [
        TIER_WEIGHTS.get(e.tier, 0.25)
        for v in verdicts
        for e in v.evidence
        if e.relation in {"supports", "contradicts"}
    ]
    authority = sum(tiers) / len(tiers) if tiers else 0.0
    coverage = len(with_evidence) / len(verdicts) if verdicts else 0.0
    supported_rate = len(supported) / len(with_evidence) if with_evidence else 0.0
    evidence_quality = coverage * (0.6 * supported_rate + 0.4 * authority)
    # Stable fact integrity 只统计 temporal_sensitivity=STABLE 的 claim；
    # 必须通过 claim_id 关联，不能把所有 FRESH/STALE/CONFLICTED 都当成稳定事实。
    claims_by_id = {claim.id: claim for claim in report.claims}
    stable_claim_ids = {
        claim.id
        for claim in report.claims
        if claim.temporal_sensitivity is TemporalSensitivity.STABLE
    }
    stable_verdicts = [
        verdict
        for verdict in verdicts
        if verdict.claim_id in stable_claim_ids
        and verdict.claim_id in claims_by_id
        and verdict.status
        in {FreshnessStatus.FRESH, FreshnessStatus.STALE, FreshnessStatus.CONFLICTED}
    ]
    stable_fresh = [
        verdict for verdict in stable_verdicts if verdict.status is FreshnessStatus.FRESH
    ]
    return {
        "evidence_quality": round(evidence_quality, 3),
        "supported_claim_rate": round(supported_rate, 3),
        "stable_fact_integrity": (
            round(len(stable_fresh) / len(stable_verdicts), 3) if stable_verdicts else None
        ),
        "authority": round(authority, 3),
    }


def weighted_view(
    *,
    accuracy: float,
    freshness: float | None,
    stale_rate: float | None,
    evidence_quality: float | None,
    completion: float,
    cost_usd: float,
    latency_s: float,
) -> float:
    """可解释的加权视图（非默认排名依据；权重显式展示）。"""
    freshness_component = (freshness or 0.0) / 100.0
    evidence_component = evidence_quality or 0.0
    stale_component = 1.0 - (stale_rate or 0.0)
    cost_component = 1.0 / (1.0 + max(cost_usd, 0.0) * 20.0)
    latency_component = 1.0 / (1.0 + max(latency_s, 0.0) / 30.0)
    score = (
        0.35 * accuracy
        + 0.20 * freshness_component
        + 0.15 * evidence_component
        + 0.10 * stale_component
        + 0.10 * completion
        + 0.05 * cost_component
        + 0.05 * latency_component
    )
    return round(score, 4)


def pareto_frontier(results: list[TaskResult]) -> dict[str, object]:
    """非支配集：最大化 accuracy/freshness，最小化 cost/latency/stale。"""
    rows = leaderboard(results)
    points: list[dict[str, float | str | bool]] = []
    for row in rows:
        points.append(
            {
                "agent_id": str(row["agent_id"]),
                "accuracy": float(row["numeric_accuracy"] or 0.0),
                "freshness": float(row["freshness_score"] or 0.0) / 100.0,
                "cost": float(row["avg_cost_usd"] or 0.0),
                "latency": float(row["avg_latency_s"] or 0.0),
                "stale": float(row["stale_rate"] or 0.0),
            }
        )

    def dominates(a: dict[str, float | str | bool], b: dict[str, float | str | bool]) -> bool:
        better_or_equal = (
            float(a["accuracy"]) >= float(b["accuracy"])
            and float(a["freshness"]) >= float(b["freshness"])
            and float(a["cost"]) <= float(b["cost"])
            and float(a["latency"]) <= float(b["latency"])
            and float(a["stale"]) <= float(b["stale"])
        )
        strictly_better = (
            float(a["accuracy"]) > float(b["accuracy"])
            or float(a["freshness"]) > float(b["freshness"])
            or float(a["cost"]) < float(b["cost"])
            or float(a["latency"]) < float(b["latency"])
            or float(a["stale"]) < float(b["stale"])
        )
        return better_or_equal and strictly_better

    for point in points:
        point["pareto"] = not any(
            dominates(other, point) for other in points if other is not point
        )
    frontier = [p["agent_id"] for p in points if p["pareto"]]
    return {
        "objectives": ["accuracy↑", "freshness↑", "cost↓", "latency↓", "stale↓"],
        "points": points,
        "frontier": frontier,
    }


def leaderboard(results: list[TaskResult]) -> list[dict[str, float | str | None]]:
    """按 agent 聚合：多维指标（不隐藏单一总分）。"""
    grouped: dict[str, list[TaskResult]] = {}
    for result in results:
        grouped.setdefault(result.agent_id, []).append(result)
    rows: list[dict[str, float | str | None]] = []
    for agent_id, items in grouped.items():
        count = len(items)
        freshness_values = [i.freshness_score for i in items if i.freshness_score is not None]
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
                "freshness_score": round(sum(freshness_values) / len(freshness_values), 1)
                if freshness_values
                else None,
                "evidence_quality": round(
                    sum(i.evidence_quality or 0.0 for i in items) / count, 3
                ),
                "claim_coverage": round(sum(i.claim_coverage for i in items) / count, 3),
                "stable_fact_integrity": round(
                    sum(i.stable_fact_integrity or 0.0 for i in items) / count, 3
                ),
                "avg_latency_s": round(sum(i.answer.latency_s for i in items) / count, 2),
                "avg_tokens": round(sum(i.answer.tokens for i in items) / count, 0),
                "avg_tokens_in": round(
                    sum(i.answer.prompt_tokens for i in items) / count, 0
                ),
                "avg_tokens_out": round(
                    sum(i.answer.completion_tokens for i in items) / count, 0
                ),
                "avg_cost_usd": round(sum(i.answer.cost_usd for i in items) / count, 6),
                "errors": sum(1 for i in items if i.error or i.answer.error),
            }
        )
    rows.sort(
        key=lambda row: (
            -(row["score"] if isinstance(row["score"], float) else 0.0),
            str(row["agent_id"]),
        )
    )
    return rows
