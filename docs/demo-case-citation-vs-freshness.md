# Demo Case: Citation is real, freshness still fails

> 用途：Tavily 赛道 60 秒核心演示。目的不是“再展示一个检测器”，而是证明 **citation ≠ freshness**。
> 数据全部来自公开 GitHub Releases，无伪造历史；使用 replay 快照，结果可复现。

## 1. 场景

一段“看起来完全可信”的答案：

```text
YAI Agent Core 当前版本是 0.24.0。
来源：https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0
```

- 引用是**真实存在**的 GitHub Release；
- 该 Release **确实支持**“0.24.0”这个说法；
- 如果只做 grounding / citation check：**通过**；
- 但今天（2026-11-01）它已经过期，因为 v0.25.0（2026-10-31）已经发布。

## 2. 预期输出

```text
as_of=2026-10-28
  status=fresh score=88 mode=replay

as_of=2026-11-01
  status=stale score=30 mode=replay
  rationale=权威来源给出了不同的值/事实，判定可能过时
```

同一个答案、同一个引用，只因为时间变了，结论从 FRESH 变为 STALE。

## 3. 演示脚本（60 秒）

| 时间 | 画面 | 旁白 |
|---|---|---|
| 0:00–0:10 | 展示答案 + 引用链接 | "This answer has a real citation. A grounding check would pass." |
| 0:10–0:20 | 打开引用：v0.24.0 确实存在且支持 | "The source is real, and it did say 0.24.0." |
| 0:20–0:35 | 跑 `/freshness/verify` as_of 2026-10-28 | "At that time, it was correct — FRESH." |
| 0:35–0:50 | 跑 as_of 2026-11-01 | "But the latest release is 0.25.0 — STALE, with evidence." |
| 0:50–1:00 | 展示修正/当前值 + 解释 | "Citation is not freshness. We audit the answer you already have." |

## 4. 运行

```powershell
# 本地（需要服务已启动）
.\.venv\Scripts\python.exe scripts\demo_citation_not_freshness.py

# 线上
.\.venv\Scripts\python.exe scripts\demo_citation_not_freshness.py --url https://yai-scout.onrender.com
```

> 线上依赖 `benchmarks/snapshots.json` 中的 32 条 GitHub Release 快照；如果线上快照为空，改用本地/预录视频。

## 5. 为什么这个 case 有差异化

- **Perplexity/Tavily Research**：生成时用 live index，通常不会给你旧答案；但我们审计的是**已有答案**。
- **Vectara HHEM / Ragas / Cleanlab**：判断“是否被证据支持”；这个 case 会通过。
- **事实核查/引用验证**：引用真实、支持 claim；但仍然不告诉你“它已过期”。
- **记忆/RAG 系统**：它们可以在上游避免过期；但企业已有答案/文档/agent output 不会自动被重写。

## 6. 证据

- Release v0.24.0: https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0
- Release v0.25.0: https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0
- 快照入库脚本: [`scripts/capture_github_history.py`](../scripts/capture_github_history.py)
- Replay 说明: [`docs/spec-temporal-replay.md`](spec-temporal-replay.md)
