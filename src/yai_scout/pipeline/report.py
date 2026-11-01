"""报告渲染（G0 桩）：先给出计划、来源清单与诚实的"未实现"说明。

后续由证据层生成正式报告（摘要 / 发现 / 证据链 / 冲突 / 不确定性 / 结论）。
"""

from __future__ import annotations

from ..domain.models import Plan, ResearchTask, SourceRecord

TIER_LABEL = {1: "T1 一手", 2: "T2 权威二手", 3: "T3 一般", 4: "T4 UGC"}


def render_report(
    task: ResearchTask,
    plan: Plan,
    sources: list[SourceRecord],
    *,
    credits: float,
    elapsed_s: float,
    failed_queries: int,
) -> str:
    domains = sorted({s.domain for s in sources if s.domain})
    lines: list[str] = [
        f"# {task.question}",
        "",
        f"> 信息截止：{task.as_of} ｜ 来源：{len(sources)} 条 / 独立域名 {len(domains)} 个 "
        f"｜ credits：{credits:g} ｜ 耗时：{elapsed_s:.1f}s ｜ 失败查询：{failed_queries}",
        "",
        "## 检索计划",
        "",
    ]
    for i, sq in enumerate(plan.sub_questions, 1):
        lines.append(f"{i}. **{sq.question}** — 查询：{' / '.join(sq.queries)}")
    lines += ["", f"_停止条件：{plan.stop_criteria}_", "", "## 已收集来源", ""]
    if not sources:
        lines.append("（没有拿到来源）")
    else:
        lines += ["| # | 来源 | 域名 | 发布时间 | 档位 |", "|---|---|---|---|---|"]
        for i, s in enumerate(sources, 1):
            title = (s.title or s.url).replace("|", "\\|")[:80]
            lines.append(
                f"| {i} | [{title}]({s.url}) | {s.domain} | {s.published_at or '未知'} "
                f"| {TIER_LABEL.get(s.tier, s.tier)} |"
            )
    lines += [
        "",
        "## 说明（G0 骨架）",
        "",
        "- 本阶段只实现 **Plan → Retrieve**：计划、来源、域名分级、credits 记账。",
        "- **证据抽取（Quote 校验）、跨来源验证、引用自审计** 尚未实现（Charter M4/M5/M7）。",
        "- 报告中的结论与引用将在证据层完成后生成；当前内容不得当作研究结论使用。",
        "",
    ]
    return "\n".join(lines)
