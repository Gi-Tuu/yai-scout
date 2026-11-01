# ruff: noqa: E501
"""Build the YAI Scout submission deck (editable PPTX)."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables" / "YAI_Scout_Submission.pptx"

BG = RGBColor(11, 15, 20)
PANEL = RGBColor(18, 24, 33)
LINE = RGBColor(36, 48, 63)
TEXT = RGBColor(230, 233, 239)
MUTED = RGBColor(139, 152, 169)
ACCENT = RGBColor(245, 165, 36)
GREEN = RGBColor(52, 211, 153)
BLUE = RGBColor(96, 165, 250)
RED = RGBColor(248, 113, 113)
WHITE = RGBColor(255, 255, 255)

FONT_CN = "Microsoft YaHei"
FONT_EN = "Segoe UI"


def _bg(slide) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = BG
    shape.line.fill.background()


def _text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: int = 16,
    color: RGBColor = TEXT,
    bold: bool = False,
    font: str = FONT_CN,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = Inches(0.02)
    frame.margin_top = frame.margin_bottom = Inches(0.02)
    lines = text.split("\n")
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = font
        run.font.color.rgb = color
    return box


def _panel(slide, x, y, w, h, *, fill=PANEL, line=LINE, radius=False):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(0.8)
    return shape


def _title(slide, kicker: str, title: str) -> None:
    _text(slide, kicker.upper(), 0.7, 0.35, 10, 0.3, size=10, color=ACCENT, bold=True)
    _text(slide, title, 0.7, 0.72, 11.8, 1.0, size=30, bold=True)


def _footer(slide, number: int, label: str = "YAI Scout · Tavily 05 · Bifrost + Tavily") -> None:
    _text(slide, label, 0.7, 7.1, 9, 0.3, size=9, color=MUTED)
    _text(slide, f"{number:02d}", 12.2, 7.05, 0.5, 0.3, size=9, color=MUTED, align=PP_ALIGN.RIGHT)


def _bullets(slide, items, x, y, w, h, *, size=16, color=TEXT, gap=0.12):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(gap)
        run = paragraph.add_run()
        run.text = "•  " + item
        run.font.size = Pt(size)
        run.font.name = FONT_CN
        run.font.color.rgb = color


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]

    # 1 — Title
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _text(slide, "GEEK ROOM · GLOBAL AI HACKATHON 2026", 0.9, 0.8, 8, 0.4, size=11, color=ACCENT, bold=True)
    _text(slide, "YAI Scout", 0.9, 1.35, 11, 1.2, size=58, bold=True, font=FONT_EN)
    _text(slide, "Evidence-first stale-answer detector", 0.9, 2.55, 11, 0.5, size=24, color=TEXT)
    _text(slide, "审计已有 AI 答案：哪些仍然成立，哪些已经过期。", 0.9, 3.15, 11, 0.45, size=17, color=MUTED)
    _panel(slide, 0.9, 4.15, 4.1, 1.3, radius=True)
    _text(slide, "PRIMARY", 1.1, 4.32, 2, 0.3, size=10, color=ACCENT, bold=True)
    _text(slide, "Tavily Track · Problem 05", 1.1, 4.6, 3.7, 0.4, size=18, bold=True)
    _panel(slide, 5.25, 4.15, 4.1, 1.3, radius=True)
    _text(slide, "BOTH TECHNOLOGIES", 5.45, 4.32, 2.5, 0.3, size=10, color=GREEN, bold=True)
    _text(slide, "Tavily · Bifrost", 5.45, 4.6, 3.7, 0.4, size=18, bold=True)
    _text(slide, "https://yai-scout.onrender.com/freshness", 0.9, 6.55, 8, 0.3, size=12, color=MUTED)
    _text(slide, "01", 12.2, 6.9, 0.5, 0.3, size=10, color=MUTED, align=PP_ALIGN.RIGHT)

    # 2 — Problem
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "The problem", "引用真实，不等于现在正确")
    _panel(slide, 0.7, 1.95, 5.6, 4.7, radius=True)
    _text(slide, "同一个回答", 1.0, 2.15, 4, 0.35, size=16, bold=True)
    _text(slide, "YAI Agent Core 当前版本是 0.24.0", 1.0, 2.55, 4.9, 0.4, size=17)
    _text(slide, "来源：GitHub Releases v0.24.0", 1.0, 2.95, 4.9, 0.3, size=12, color=MUTED)
    _panel(slide, 1.0, 3.55, 2.35, 1.15, fill=RGBColor(22, 40, 33), line=GREEN, radius=True)
    _text(slide, "2026-10-28", 1.15, 3.7, 2, 0.3, size=11, color=MUTED)
    _text(slide, "FRESH 88", 1.15, 4.0, 2, 0.4, size=22, color=GREEN, bold=True)
    _panel(slide, 3.65, 3.55, 2.35, 1.15, fill=RGBColor(45, 28, 22), line=RED, radius=True)
    _text(slide, "2026-11-01", 3.8, 3.7, 2, 0.3, size=11, color=MUTED)
    _text(slide, "STALE 30", 3.8, 4.0, 2, 0.4, size=22, color=RED, bold=True)
    _text(slide, "页面存在、引用真实、内容确实支持——但它已经是旧值。", 1.0, 5.15, 4.9, 0.8, size=15, color=MUTED)
    _panel(slide, 6.65, 1.95, 6.0, 4.7, radius=True)
    _text(slide, "为什么现有工具不够", 6.95, 2.15, 4, 0.35, size=16, bold=True)
    _bullets(
        slide,
        [
            "Citation / grounding：只判断“是否有证据支持”",
            "RAG freshness：多在检索/索引层，要求改造上游",
            "模型记忆：无法解释“为什么现在不对”",
            "人工核查：贵、慢、不可复现",
        ],
        6.95,
        2.65,
        5.4,
        2.6,
        size=15,
    )
    _text(slide, "缺少的是：对已有答案的 claim 级、可复现、可解释的过期审计。", 6.95, 5.55, 5.3, 0.7, size=14, color=ACCENT)
    _footer(slide, 2)

    # 3 — Solution flow
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "The product", "不是再生成答案，而是审计已有答案")
    steps = [
        ("01", "Answer", "任意模型/Agent 的答案"),
        ("02", "Claims", "拆成可核验事实句"),
        ("03", "Temporal", "stable / slow / sensitive / volatile"),
        ("04", "Research", "Tavily 取当前来源"),
        ("05", "Verdict", "FRESH / STALE / CONFLICTED / INSUFFICIENT"),
        ("06", "Correct", "当前值 + 修正建议 + 证据"),
    ]
    for index, (number, heading, body) in enumerate(steps):
        x = 0.65 + index * 2.1
        _panel(slide, x, 2.0, 1.9, 2.45, radius=True)
        _text(slide, number, x + 0.15, 2.15, 0.8, 0.3, size=11, color=ACCENT, bold=True)
        _text(slide, heading, x + 0.15, 2.5, 1.6, 0.4, size=17, bold=True, font=FONT_EN)
        _text(slide, body, x + 0.15, 2.95, 1.6, 1.2, size=11, color=MUTED)
    _panel(slide, 0.7, 4.95, 11.9, 1.45, radius=True)
    _text(slide, "关键边界", 0.95, 5.1, 2, 0.3, size=11, color=ACCENT, bold=True)
    _text(slide, "模型负责“抽取/判断/改写”；确定性代码负责“状态、预算、证据、评分”。", 0.95, 5.45, 11.3, 0.45, size=17, bold=True)
    _text(slide, "Freshness 只回答“是否过期”；Accuracy 另由 evidence gate 管理，默认不自动覆盖。", 0.95, 5.95, 11.3, 0.3, size=12, color=MUTED)
    _footer(slide, 3)

    # 4 — Architecture
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Architecture", "Tavily 负责研究，Bifrost 负责模型请求")
    boxes = [
        (0.7, 1.95, 3.0, 1.1, "UI / API", "freshness · inspector · compare", BLUE),
        (0.7, 3.45, 3.0, 1.25, "Tavily", "live web research", GREEN),
        (0.7, 5.05, 3.0, 1.1, "Evidence store", "SQLite · snapshots · anchors", MUTED),
        (4.55, 1.95, 3.3, 1.1, "Bifrost gateway", "OpenAI-compatible routing/logs", ACCENT),
        (4.55, 3.45, 3.3, 1.25, "Model provider", "claim extraction · assessment", TEXT),
        (4.55, 5.05, 3.3, 1.1, "Deterministic engine", "status · scoring · budgets", BLUE),
        (8.85, 1.95, 3.55, 3.0, "Freshness report", "per-claim status\nsource links\nscore breakdown\ncorrection", GREEN),
        (8.85, 5.05, 3.55, 1.1, "Audit / governance", "candidate · approve · rollback", ACCENT),
    ]
    for x, y, w, h, heading, body, color in boxes:
        _panel(slide, x, y, w, h, radius=True)
        _text(slide, heading, x + 0.2, y + 0.15, w - 0.4, 0.35, size=16, bold=True, color=color)
        _text(slide, body, x + 0.2, y + 0.55, w - 0.4, h - 0.6, size=12, color=MUTED)
    _text(slide, "→", 3.9, 2.25, 0.5, 0.4, size=22, color=MUTED)
    _text(slide, "→", 3.9, 3.75, 0.5, 0.4, size=22, color=MUTED)
    _text(slide, "→", 8.05, 2.25, 0.6, 0.4, size=22, color=MUTED)
    _footer(slide, 4)

    # 5 — How claims are judged
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "How it works", "每个 claim 都有可解释的判定链")
    _panel(slide, 0.7, 1.9, 5.7, 4.95, radius=True)
    _text(slide, "判定步骤", 0.95, 2.1, 3, 0.3, size=12, color=ACCENT, bold=True)
    _bullets(
        slide,
        [
            "抽取可能过期的事实句（价格/版本/许可证/日期…）",
            "判断时间敏感性：stable → volatile",
            "Tavily 找当前来源，记录时间、tier、内容 hash",
            "关系判断：supports / contradicts / mentions",
            "确定性公式：relation + recency + authority + coverage",
            "输出状态、分数拆解、理由、当前值、修正建议",
        ],
        0.95,
        2.5,
        5.1,
        3.8,
        size=14,
    )
    _panel(slide, 6.7, 1.9, 5.9, 2.35, radius=True)
    _text(slide, "状态不是“猜测”", 6.95, 2.08, 4, 0.3, size=12, color=ACCENT, bold=True)
    _bullets(
        slide,
        [
            "FRESH：权威来源支持，且时间有效",
            "STALE：权威来源给出不同值",
            "CONFLICTED：多个权威来源互相矛盾",
            "INSUFFICIENT / UNKNOWN：证据不足/无法判断",
        ],
        6.95,
        2.45,
        5.2,
        1.65,
        size=13,
    )
    _panel(slide, 6.7, 4.5, 5.9, 2.35, radius=True)
    _text(slide, "可复现", 6.95, 4.68, 3, 0.3, size=12, color=GREEN, bold=True)
    _text(slide, "as-of replay：固定 target_time + 快照，同一个答案\n2026-10-28 FRESH → 2026-11-01 STALE", 6.95, 5.05, 5.2, 0.9, size=15)
    _text(slide, "Policy / weights 版本化；LLM 不产出分数。", 6.95, 6.0, 5.2, 0.3, size=11, color=MUTED)
    _footer(slide, 5)

    # 6 — Differentiation
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Why different", "审计层，而不是又一个答案引擎")
    cards = [
        ("Post-hoc", "审计已有答案，不要求换模型/重建 RAG"),
        ("Support ≠ Freshness", "引用真实也可能过期；两者分开判定"),
        ("Current value", "不只红绿灯，给出当前值和修正"),
        ("As-of replay", "同一答案在不同时间得到不同结论"),
        ("Evidence governance", "anchor → candidate → gate → approve/rollback"),
        ("Honest boundaries", "默认不自动覆盖；证据与推断分开"),
    ]
    for index, (heading, body) in enumerate(cards):
        col = index % 3
        row = index // 3
        x = 0.7 + col * 4.05
        y = 1.95 + row * 2.35
        _panel(slide, x, y, 3.8, 2.05, radius=True)
        _text(slide, heading, x + 0.25, y + 0.2, 3.3, 0.4, size=18, bold=True, color=ACCENT if row == 0 else TEXT)
        _text(slide, body, x + 0.25, y + 0.75, 3.25, 1.0, size=14, color=MUTED)
    _footer(slide, 6)

    # 7 — Fixed demo
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Evidence", "固定 demo：同一个答案，两个时间点")
    rows = [
        ("Python 3.12 于 2023 发布", "FRESH 70", "稳定事实，旧来源不误伤", GREEN),
        ("YAI 0.24.0 @ 2026-10-28", "FRESH 88", "当时正确", GREEN),
        ("YAI 0.24.0 @ 2026-11-01", "STALE 30", "citation ≠ freshness", RED),
        ("YAI 0.25.0 @ 2026-11-01", "FRESH 88", "当前值", GREEN),
    ]
    _text(slide, "case", 0.85, 1.95, 4.2, 0.3, size=10, color=MUTED, bold=True)
    _text(slide, "verdict", 5.3, 1.95, 2.3, 0.3, size=10, color=MUTED, bold=True)
    _text(slide, "why", 7.6, 1.95, 4.5, 0.3, size=10, color=MUTED, bold=True)
    for index, (case, verdict, why, color) in enumerate(rows):
        y = 2.4 + index * 1.0
        _panel(slide, 0.7, y - 0.12, 12.0, 0.78, radius=True)
        _text(slide, case, 0.9, y, 4.3, 0.4, size=15)
        _text(slide, verdict, 5.3, y, 2.2, 0.4, size=17, bold=True, color=color)
        _text(slide, why, 7.6, y, 4.6, 0.4, size=13, color=MUTED)
    _text(slide, "可离线回放：scripts/demo_fixed_cases.py（缓存真实 API 响应，不依赖网络）", 0.7, 6.55, 11, 0.3, size=12, color=MUTED)
    _footer(slide, 7)

    # 8 — Benchmark evidence
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Supporting evidence", "Benchmark 是评测方法，不是第二个提交")
    _panel(slide, 0.7, 1.9, 6.0, 4.95, radius=True)
    _text(slide, "24 tasks", 0.95, 2.1, 5, 0.4, size=22, bold=True)
    _text(slide, "21 public + 3 compromised · 4 categories", 0.95, 2.55, 5, 0.3, size=13, color=MUTED)
    _bullets(
        slide,
        [
            "stable / time_sensitive / changed / conflicting",
            "HTTP / Python / CLI adapters（不重写 Agent）",
            "Accuracy · freshness · evidence · cost · latency",
            "Pareto frontier，而不是单一黑箱分",
            "manifest + config_hash + result_hash + verify",
        ],
        0.95,
        3.05,
        5.3,
        2.8,
        size=13,
    )
    _panel(slide, 6.95, 1.9, 5.65, 2.25, radius=True)
    _text(slide, "为什么保留", 7.2, 2.1, 4, 0.3, size=12, color=ACCENT, bold=True)
    _text(slide, "它让“freshness 是否有效”可测量、可复现；\n也展示我们如何比较不同 Agent 架构。", 7.2, 2.45, 5.0, 1.0, size=15)
    _panel(slide, 6.95, 4.4, 5.65, 2.45, radius=True)
    _text(slide, "边界", 7.2, 4.58, 3, 0.3, size=12, color=RED, bold=True)
    _text(slide, "demo 规模，不是学术 leaderboard；\n明确不声称完成 Bifrost Track 02。", 7.2, 4.95, 5.0, 1.0, size=14, color=MUTED)
    _footer(slide, 8)

    # 9 — Bifrost proof
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Both technologies", "Bifrost 不是 logo，是实际的模型网关")
    _panel(slide, 0.7, 1.9, 5.4, 4.95, fill=RGBColor(9, 12, 17), line=LINE, radius=True)
    _text(slide, "LOCAL VERIFICATION · 2026-11-02", 0.95, 2.1, 4.5, 0.3, size=10, color=GREEN, bold=True)
    _text(
        slide,
        'healthz\n  "gateway": "bifrost"\n  "model": "openai/deepseek/...-1017"\n\nBifrost log\n  POST /v1/chat/completions 200\n  user_agent=python-httpx/0.28.1\n\nFreshness\n  statuses=["stale"]',
        0.95,
        2.55,
        4.8,
        3.8,
        size=12,
        color=GREEN,
        font="Consolas",
    )
    _panel(slide, 6.6, 1.9, 6.0, 2.1, radius=True)
    _text(slide, "Tavily", 6.85, 2.05, 2, 0.35, size=16, bold=True, color=GREEN)
    _text(slide, "live research：找当前来源、抓内容、记录来源等级", 6.85, 2.45, 5.3, 0.6, size=13, color=MUTED)
    _panel(slide, 6.6, 4.2, 6.0, 2.1, radius=True)
    _text(slide, "Bifrost", 6.85, 4.35, 2, 0.35, size=16, bold=True, color=ACCENT)
    _text(slide, "模型请求：claim 抽取 / 关系判断 / 修正；provider routing + logs", 6.85, 4.75, 5.3, 0.8, size=13, color=MUTED)
    _text(slide, "公开 Render 当前为 direct fallback；视频/本地演示展示 Bifrost，材料中不混淆。", 0.7, 6.95, 12, 0.3, size=10, color=MUTED)
    _footer(slide, 9)

    # 10 — Guardrails
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Engineering", "把“看起来能跑”变成“可复现、可审计”")
    stats = [
        ("136", "tests", "Python 3.11 / 3.12"),
        ("CI", "green", "lint · types · tests · Docker"),
        ("32", "snapshots", "real GitHub release history"),
        ("0", "auto-updates", "AUTO_UPDATE=false by default"),
    ]
    for index, (value, label, note) in enumerate(stats):
        x = 0.7 + index * 3.05
        _panel(slide, x, 1.95, 2.8, 1.75, radius=True)
        _text(slide, value, x + 0.2, 2.1, 2.4, 0.6, size=30, bold=True, color=ACCENT)
        _text(slide, label, x + 0.2, 2.7, 2.4, 0.3, size=12, color=TEXT)
        _text(slide, note, x + 0.2, 3.0, 2.4, 0.4, size=10, color=MUTED)
    _bullets(
        slide,
        [
            "确定性代码负责状态/评分/预算；LLM 输出 schema 校验 + quote 必须是原文子串",
            "Tavily 失败 → 降级 INSUFFICIENT；模型失败 → 规则兜底，不伪造证据",
            "live anchor fetch 默认关闭；allowlist + 公网 IP + 固定 IP + Host/SNI",
            "公开 demo 限流；admin 端点 token 保护；成本预算 guard",
        ],
        0.9,
        4.1,
        11.6,
        2.4,
        size=13,
    )
    _footer(slide, 10)

    # 11 — Limits
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _title(slide, "Honest limits", "哪些现在还不能吹")
    items = [
        ("人工标签", "60/60 与隐藏 key 一致 = 按规则标注，\n不是独立 ground truth；AUTO_UPDATE 保持关闭。"),
        ("Benchmark", "24 题 demo 规模，不是学术 leaderboard；\n不作为 primary submission。"),
        ("Bifrost", "本地/视频已真实验证；公开 Render 仍是 direct，\n除非部署公网 Bifrost。"),
        ("Replay", "Wayback 不可达；replay 覆盖 GitHub Release 类事实，\n无快照时标 simulated。"),
    ]
    for index, (heading, body) in enumerate(items):
        col = index % 2
        row = index // 2
        x = 0.7 + col * 6.15
        y = 1.95 + row * 2.35
        _panel(slide, x, y, 5.85, 2.05, radius=True)
        _text(slide, heading, x + 0.25, y + 0.2, 5.2, 0.35, size=17, bold=True, color=RED)
        _text(slide, body, x + 0.25, y + 0.7, 5.2, 1.1, size=13, color=MUTED)
    _footer(slide, 11)

    # 12 — Close
    slide = presentation.slides.add_slide(blank)
    _bg(slide)
    _text(slide, "TRY IT", 0.9, 0.9, 4, 0.35, size=11, color=ACCENT, bold=True)
    _text(slide, "审计一条答案，看它是否还成立。", 0.9, 1.4, 11.5, 0.9, size=36, bold=True)
    _text(slide, "https://yai-scout.onrender.com/freshness", 0.9, 2.6, 11, 0.5, size=22, color=GREEN)
    _panel(slide, 0.9, 3.6, 5.6, 2.4, radius=True)
    _text(slide, "Demo path", 1.15, 3.8, 4, 0.3, size=11, color=ACCENT, bold=True)
    _text(slide, "粘贴 YAI 0.24.0 回答\nas_of = 2026-11-01\n看 STALE + 当前值 0.25.0", 1.15, 4.2, 5.0, 1.2, size=15)
    _panel(slide, 6.9, 3.6, 5.5, 2.4, radius=True)
    _text(slide, "Repo", 7.15, 3.8, 4, 0.3, size=11, color=ACCENT, bold=True)
    _text(slide, "github.com/Gi-Tuu/yai-scout\nREADME · docs/submission.md\nscripts/verify_bifrost.py", 7.15, 4.2, 4.9, 1.2, size=14)
    _text(slide, "Bifrost by Maxim AI × Tavily · Geek Room Global AI Hackathon 2026", 0.9, 6.75, 11.5, 0.3, size=11, color=MUTED)
    _footer(slide, 12)

    presentation.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)

