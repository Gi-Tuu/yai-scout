# YAI Scout

> Evidence First, Answers Second.
> 状态：**G0 骨架已跑通 / 赛题已发布 / 选题待官方确认** · 2026-11-01

YAI Scout 是参加 **Geek Room Global AI Hackathon**（2026-10-09 → 11-29，线上，个人可参赛）的作品：一个可审计、证据优先的研究 Agent。本仓库同时保存预研材料与实现代码。

## 交付物

| 文件 | 内容 |
|---|---|
| [docs/charter.md](docs/charter.md) | **主交付物**：完整 Project Charter（赛事核查、赛道策略、架构、YAI 复用、MVP、评测、成本工期、仓库结构、倒排计划、风险） |
| [research/competition-facts.md](research/competition-facts.md) | 赛事事实核查底稿 + Tavily/合作方/模型 API 额度与价格 + 北京时间换算 |
| [research/yai-interface-audit.md](research/yai-interface-audit.md) | YAI Agent Core v0.25.0 可复用接口审计、已知坑与依赖方式 |
| [docs/tavily-setup.md](docs/tavily-setup.md) | Tavily 接入决策：Windows 下走 REST API（不装 CLI/全局 Skills）、key 存放与验证 |
| [docs/hackathon-rules-report.md](docs/hackathon-rules-report.md) | **赛事调查全文**：赛题、双赛道规则（含 4 处官方口径冲突）、奖金修正、选题与开发建议 |
| [docs/adr/0001-track-selection.md](docs/adr/0001-track-selection.md) | 选题决策：Bifrost-02 + Tavily-01 整合方案（待主办方确认） |
| [research/problem-statements/hackculture-event.json](research/problem-statements/hackculture-event.json) | 官方平台事件原始 JSON（时间线/提交字段/公告/奖项）存档 |
| [scripts/tavily_smoke.py](scripts/tavily_smoke.py) | Tavily 冒烟测试（只打印标题/URL/credits，不打印 key） |

## 现在能跑什么（G0 骨架）

**输入问题 → 规则计划 → Tavily 多查询检索 → 归一化/域名分级 → SSE 实时进度 → 来源清单 + 报告桩**

已实现：
- FastAPI + SSE 事件流（断线可按 `Last-Event-ID` 重放），单页研究控制台；
- SQLite 持久化（任务/计划/来源/事件/成本），来源按 canonical URL 去重；
- Tavily REST 适配器：有 key 走 Bearer，无 key 自动 keyless（有限速）；
- credits 记账、单 run 预算（默认 32 credits）与墙钟降级；
- 21 个测试 + ruff + mypy(strict) 全绿。

未实现（G0 之后按 Charter 推进）：证据抽取与引文校验（M4）、跨来源验证（M5）、带引用报告与自审计（M7）。

### 本地运行

```powershell
uv sync --extra dev
copy .env.example .env          # 填 TAVILY_API_KEY（不填则走 keyless 模式）
.\.venv\Scripts\python.exe -m uvicorn yai_scout.api.app:app --port 8010
# 打开 http://127.0.0.1:8010
```

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 测试
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy
```

## 关键结论

- 个人参赛合规；**真实截止 = 北京时间 2026-11-16 02:29**（11/15 23:59 IST），题目 **11/1 02:30** 公布（北京时间）。
- 题目/赛道截至 11/1 10:20 仍显示 `REVEALING SOON`（官网未更新）→ 采用「轨道无关内核 + 48h 适配」，默认最匹配 **Tavily Track**；题目以 Discord 公告为准。
- 复用 YAI v0.25.0（tag `614f3106...`）作嵌入式 Agent 内核；Scout 自研证据台账、跨来源验证与引用自审计。
- 现金支出目标 ≤ $20；单份报告边际成本 ≈$0.06–0.25；Tavily 免费 1,000 credits/月。

## 下一步

1. **等题目**：官网仍 `REVEALING SOON`；在 Discord 看到题目后按 Charter §3.3 做 Track 打分与 ADR-000。
2. **配 Tavily key**：写入 `.env` 的 `TAVILY_API_KEY`（当前走 keyless，有限速）；有学生身份可申请学生计划。
3. **实现 M4/M5/M7**：证据抽取 + 引文逐字校验 → 跨来源验证 → 带引用报告与自审计。
4. **注册与入群**（若尚未）：https://hackculture.io/hackathons/register/ai-global-hackathon + 官方 Discord（邀请 2026-11-08 到期）。

## 合规边界（本项目已遵守）

- 未创建任何收费资源；
- 未修改 YAI 主仓库（只读审计；该仓库原有未提交改动与本项目无关）；
- 未进行任何远程提交或报名操作（需本人确认）。

