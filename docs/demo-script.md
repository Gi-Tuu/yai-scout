# 比赛 Demo 脚本（B2 / T1）

> 用途：录视频、现场答辩、评审 5 小时窗口内的 3 分钟展示。
> 原则：先给结论与差异，再给证据；每个数字都能点开；失败有录屏兜底。

## 0. 录制前检查（10 分钟）

- 服务：`http://127.0.0.1:8010`，`/api/healthz` 显示 `tavily: key`、`llm: true`；
- 端口 9101 的外部 Echo Agent 已启动（跨架构演示）；
- 预置好 3 份 Freshness 报告（stale / fresh / insufficient）与 1 次 benchmark run；
- 浏览器缩放 125%，关闭无关标签；录屏 1080p、字幕中英双语。

## 1. Project B — Freshness（2:00）

| 时间 | 画面 | 旁白 |
|---|---|---|
| 0:00–0:15 | 粘贴一段"看起来正常"的答案（含旧价格 + 一个稳定事实） | "This answer looks fine. Is it still true?" |
| 0:15–0:40 | claim 列表出现，标出 time sensitivity（sensitive / stable） | "We split the answer into claims and classify how fast each fact changes." |
| 0:40–1:05 | 点开 stale claim：显示原文、Tavily 证据、来源时间、判定理由 | "The official source says 1,000 — the answer says 500. Evidence, not vibes." |
| 1:05–1:25 | 分数拆解：relation / recency / authority / coverage 四条进度条 | "Freshness is explainable: every point comes from evidence." |
| 1:25–1:45 | 点开 stable claim：来源很旧但判 FRESH | "Old source is not automatically stale — we classify first." |
| 1:45–2:00 | 修正建议 + 导出 Markdown | "And it tells you what the current value should be." |

## 2. Project A — Benchmark（2:00）

| 时间 | 画面 | 旁白 |
|---|---|---|
| 0:00–0:20 | 三个 Agent：HTTP 外部 / Python / LLM RAG | "Different architectures, same tasks." |
| 0:20–0:45 | 一键运行 12 题，进度条滚动 | "Same dataset, same target time, same budget." |
| 0:45–1:15 | 多维榜单：Accuracy / Freshness / Stale / Evidence / Cost / Latency，★ Pareto | "No single opaque score — you see the trade-offs." |
| 1:15–1:40 | 点开一个 bad case：答案对但引用旧数据 → Freshness 低 | "Correct but outdated is not good enough." |
| 1:40–2:00 | config_hash + 重跑一致 | "Reproducible: same config, same result." |

## 3. 合并版（4 分钟，若平台只允许一个视频）

- 0:00–0:20 统一开场：两个独立作品、共享底座、赛题映射（Bifrost-02 / Tavily-01）
- 0:20–2:10 Project A
- 2:10–4:00 Project B
- 结尾 10 秒：仓库 / 在线 Demo / 团队

## 4. 评审可能追问（准备答案）

1. **"这不就是 Tavily Research / Perplexity 吗？"** → 我们做的是 claim 级证据与 freshness 排序，不是再生成一段答案；Benchmark 还能横向比较不同 Agent。
2. **"Freshness 分数怎么来的？"** → 决策表 + 确定性公式 + 权重版本；20 条标注 20/20（规则层），详见 `docs/freshness-spec.md`。
3. **"历史回放是真的吗？"** → 当前网络无法访问 Wayback，跨时间对比标 `simulated` 并明示；有真实快照才升级 replay，绝不伪造。
4. **"为什么两个项目？"** → 主办方确认可双作品；共享底座、独立入口、独立交付。
5. **"成本多少？"** → 单份 Freshness 报告 ≈ 4 credits + $0.001；一次 12 题 × 3 Agent 评测 ≈ 40 credits + $0.01（按当前额度）。

## 5. 失败兜底

- 网络失败 → 播预录视频 + 本地 fixtures；
- LLM 超时 → 规则版 claim 抽取仍可用；
- Tavily 限流 → 切 keyless/缓存，并在画面标注"degraded mode"。
