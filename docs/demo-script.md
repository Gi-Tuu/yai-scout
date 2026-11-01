# 比赛 Demo 脚本（B2 / T1）— v0.2.1

> 用途：录视频、现场答辩、评审 5 小时窗口内的 3 分钟展示。
> 原则：先给结论与差异，再给可点开的证据；失败有录屏兜底。
> 在线 Demo：<https://yai-scout.onrender.com>（免费层休眠，首次访问 30–90s，录前先预热）。

## 0. 录制前检查（10 分钟）

- 打开 <https://yai-scout.onrender.com/api/healthz>，确认：
  `version=0.2.1`、`tavily.mode=key`、`llm.available=true`、`snapshots=32`；
- 提前 2 分钟访问一次首页，避免冷启动入镜；
- 预置：1 份 stale 报告、1 份 fresh 报告、1 次 benchmark run；
- 浏览器缩放 110–125%，关闭无关标签；1080p；建议英文旁白 + 英文字幕；
- **录屏兜底**：所有关键页面提前截屏/预录 30s，网络失败时切预录。

## 1. 开场（20s，合并版用）

> "Two independent projects, one evidence core."
> 画面：首页两张卡片 → `/benchmark`、`/freshness`。

- Project A → Bifrost Track, Problem 02（agent benchmarking）
- Project B → Tavily Track, Problem 01（stale-answer detection）
- 主办方确认：合并提交、两轨分别评审。

## 2. Project B — Freshness（90s）

| 时间 | 画面 | 旁白 |
|---|---|---|
| 0:00–0:10 | 粘贴一段"看起来正常"的答案（含旧价格 + 一个稳定事实） | "This answer looks fine. Is it still true?" |
| 0:10–0:25 | claim 列表 + time sensitivity 标签 | "We split the answer into claims and classify how fast each fact changes." |
| 0:25–0:45 | 点开 stale claim：原文、Tavily 证据、发布时间、判定理由 | "The official source says 1,000 — the answer says 500. Evidence, not vibes." |
| 0:45–1:00 | 分数拆解：relation / recency / authority / coverage | "Every point comes from evidence and a versioned policy." |
| 1:00–1:15 | 点开 stable claim：来源旧但 FRESH | "Old source is not automatically stale — classify first." |
| 1:15–1:30 | 修正建议 + Export Markdown / `/inspector` | "And it tells you the current value, with an auditable report." |

可选加分镜头（+10s）：`/compare` 选两份 replay 报告，显示
`mode=replay`、10-28 STALE → 11-01 FRESH、Δ+64。

## 3. Project A — Benchmark（90s）

| 时间 | 画面 | 旁白 |
|---|---|---|
| 0:00–0:15 | `/benchmark`：三个 Agent（HTTP 外部 / Python / LLM RAG） | "Different architectures, same tasks." |
| 0:15–0:35 | 运行 3–6 题（不要跑满 24 题，控制时间） | "Same dataset, target time and budget." |
| 0:35–1:00 | 多维榜单：Accuracy / Freshness / Stale / Evidence / Cost / Latency，★ Pareto | "No single opaque score — you see the trade-offs." |
| 1:00–1:15 | 打开 bad case：答案对但引用旧数据 | "Correct but outdated is not good enough." |
| 1:15–1:30 | 打开 run 详情：`config_hash` + `result_hash` + verify 结果 | "Reproducible and verifiable: manifest, result hash, verify endpoint." |

## 4. 结尾（15s）

- GitHub：`github.com/Gi-Tuu/yai-scout`
- 在线 Demo：`yai-scout.onrender.com`
- 两轨映射 + 99 tests + CI + 局限（Wayback 不可达、hidden 已 compromised）

## 5. 评审可能追问（准备答案）

1. **"这不就是 Perplexity/Tavily Research 吗？"** → 我们输出 claim 级证据与 freshness 排序，不是再生成答案；Benchmark 可横向比较不同 Agent 架构。
2. **"分数怎么来的？"** → 决策表 + 确定性公式 + `POLICY_VERSION/WEIGHTS_VERSION`；20 条规则标注 20/20，MAE 12.06（`docs/freshness-eval.md`）。
3. **"历史回放是真的吗？"** → 网页历史受网络限制；GitHub Releases 官方历史是真实 replay；无快照时标 `simulated`，绝不伪造。
4. **"为什么两个项目？"** → 主办方确认可合并提交、按赛道分别评审；技术上是两个独立入口/交付。
5. **"成本？"** → 单份报告 ≈ 2–4 credits；3–6 题 × 3 Agent ≈ 10–20 credits；公开 Demo 有 4/min、60/日、20/日限流。
6. **"hidden 题保密吗？"** → 不宣称保密：3 道题已进入公开历史，标记 `compromised`；公开 API 不返回、不执行，私有替代题在仓库外。
7. **"结果可复现吗？"** → 同 manifest 同 result hash（确定性 Agent，CI 测试 `test_same_manifest_and_results_are_reproducible`）；真实 Agent 的延迟/成本会变，但配置可审计。

## 6. 失败兜底

- 网络失败 → 播预录视频 + 本地 fixtures；
- LLM 超时 → 规则版抽取仍可用；
- Tavily 限流 → keyless/缓存，画面标注 "degraded mode"；
- Demo 冷启动 → 提前预热 + 视频中注明 30–90s。

## 7. 短版（60s，用于表单/社交）

1. 首页两卡片（5s）
2. Freshness：stale claim + 证据 + 分数拆解（25s）
3. Benchmark：3 Agent 榜单 + Pareto + verify（25s）
4. 结尾：GitHub + Demo URL（5s）

