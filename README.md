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
| [research/organizer-reply.md](research/organizer-reply.md) | 主办方 "All yes." 确认记录（双赛道/双作品/整合均可） |
| [research/organizer-followup-email.md](research/organizer-followup-email.md) | **第二封追问邮件**（提交机制/credits，可直接复制发送） |
| [research/organizer-reply/](research/organizer-reply/) | 主办方回复原件/截图存档目录 |
| [docs/adr/0001-track-selection.md](docs/adr/0001-track-selection.md) | ~~整合方案~~（已被 ADR-0002 取代） |
| [docs/adr/0002-dual-project-strategy.md](docs/adr/0002-dual-project-strategy.md) | **决策**：双赛道、双独立作品、共享技术底座 |
| [docs/charter-benchmark.md](docs/charter-benchmark.md) | Project A 立项：Benchmark（Bifrost-02） |
| [docs/charter-freshness.md](docs/charter-freshness.md) | Project B 立项：Freshness（Tavily-01） |
| [docs/architecture-shared.md](docs/architecture-shared.md) | 共享底座架构、契约、数据模型、数据流、部署 |
| [docs/yai-reuse.md](docs/yai-reuse.md) | YAI 复用清单与许可证核对（MIT，非 AGPL） |
| [docs/api-resources.md](docs/api-resources.md) | Tavily / Bifrost / 模型 API 额度与成本评估 |
| [docs/dual-project-plan.md](docs/dual-project-plan.md) | MVP 验收、14 天排期、风险、提交材料矩阵 |
| [docs/differentiation-spec.md](docs/differentiation-spec.md) | **v2 差异化总规格**：六项能力、P0/P1/P2、验收、Demo、现状差距 |
| [docs/spec-freshness-scoring.md](docs/spec-freshness-scoring.md) | 时间敏感性分类、Freshness Score、关系语义、边界测试向量 |
| [docs/spec-benchmark-adapter.md](docs/spec-benchmark-adapter.md) | Agent Adapter 协议、Dataset schema、指标、成本模型、Pareto |
| [docs/spec-temporal-replay.md](docs/spec-temporal-replay.md) | As-of 时间回放：快照、不可变运行、漂移比较 |
| [docs/benchmark.md](docs/benchmark.md) | 已实现 Benchmark/Detector 的说明（demo v0） |
| [research/problem-statements/hackculture-event.json](research/problem-statements/hackculture-event.json) | 官方平台事件原始 JSON（时间线/提交字段/公告/奖项）存档 |
| [scripts/tavily_smoke.py](scripts/tavily_smoke.py) | Tavily 冒烟测试（只打印标题/URL/credits，不打印 key） |

## 现在能跑什么

**输入问题 → 规则计划 → Tavily 多查询检索 → 归一化/域名分级 → SSE 实时进度 → 来源清单 + 报告桩**

已实现（P0，2026-11-01）：
- **两个独立入口**：`/benchmark`（B2）、`/freshness`（T1），统一 landing 在 `/`；旧入口 `/bench`、`/detector` 保留别名；`SCOUT_MODE=benchmark|freshness` 可单开。
- **Freshness（T1）**：LLM claim 抽取 + 规则兜底、时间敏感性四档分类、Tavily 实时核验、关系（supports/contradicts/mentions）、状态机（FRESH/STALE/CONFLICTED/INSUFFICIENT/UNKNOWN）、可空分数 + breakdown + confidence、修正建议。
- **Benchmark（B2）**：12 题四类数据集（stable / time_sensitive / changed / conflicting）、`scout-adapter/1.0` HTTP 协议（`/manifest` + `/run`）、外部示例 Agent、Runner、多维排行榜（准确率/Freshness/Stale/证据质量/Claim 覆盖/成本/时延）、`config_hash` 可复现。
- Tavily REST（key 模式）+ DeepSeek LLM（`deepseek-v4.1-flash-1017`），无 key 时自动降级。
- **59 个测试 + ruff + mypy(strict) 全绿**。

页面：`/benchmark` 榜单 · `/freshness` 检测器 · `/research` 旧研究控制台。
未实现（P1）：Evidence Inspector、Pareto 可视化、24 题、Wayback 历史快照与漂移对比、更多 Adapter。详见 [differentiation-spec.md](docs/differentiation-spec.md)。

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

1. **按 [ADR-0002](docs/adr/0002-dual-project-strategy.md) 执行**：Project A = Benchmark（`/benchmark`），Project B = Freshness（`/freshness`），共享 `scout_core`。
2. **等两个 key/答复**：DeepSeek key（当前缺失）；主办方对"双作品如何提交"的回复（默认一仓库两入口 + 合并视频）。
3. **11/02 冻结共享契约**（见 [共享架构](docs/architecture-shared.md)），之后并行开发两个 app。
4. **11/12 功能冻结**；11/15 12:00 前提交（详见 [双项目计划](docs/dual-project-plan.md)）。

## 合规边界（本项目已遵守）

- 未创建任何收费资源；
- 未修改 YAI 主仓库（只读审计；该仓库原有未提交改动与本项目无关）；
- 未进行任何远程提交或报名操作（需本人确认）。


