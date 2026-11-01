"""G0 计划器：规则生成子问题与检索查询（不花模型 token）。

后续接入 LLM 时替换为结构化输出（Planner schema），接口保持不变。
"""

from __future__ import annotations

from ..domain.models import Plan, SubQuestion


def build_plan(question: str, as_of: str) -> Plan:
    """把问题拆成 3 个子问题、4 条查询；确定性输出，便于测试与离线回放。"""
    q = " ".join(question.split()).strip()
    queries = [
        q,
        f"{q} official report data",
        f"{q} 2026 latest",
        f"{q} analysis criticism",
    ]
    sub_questions = [
        SubQuestion(
            id="sq1",
            question="核心事实与关键数字是什么？",
            queries=[queries[0], queries[1]],
            required_source_types=["official", "data"],
        ),
        SubQuestion(
            id="sq2",
            question="一手/官方来源怎么说？",
            queries=[queries[1], queries[2]],
            required_source_types=["official"],
        ),
        SubQuestion(
            id="sq3",
            question="最新进展与争议点是什么？",
            queries=[queries[2], queries[3]],
            required_source_types=["media", "analysis"],
        ),
    ]
    return Plan(
        sub_questions=sub_questions,
        stop_criteria="每个子问题至少 2 个独立域名来源，或预算耗尽",
        generated_by="rules",
    )


def plan_queries(plan: Plan) -> list[str]:
    """按出现顺序去重所有查询。"""
    seen: set[str] = set()
    out: list[str] = []
    for sq in plan.sub_questions:
        for query in sq.queries:
            if query not in seen:
                seen.add(query)
                out.append(query)
    return out
