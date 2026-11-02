# YAI Scout Freshness — Primary Submission

> **Tavily Track, Problem 05 (track-local Tavily-01) · Stale-answer detector**  
> 不是再生成一个答案，而是审计“你已有的答案”是否仍然成立。  
> **Bifrost 角色**：所有 claim 抽取 / 关系判断 / 修正建议的模型请求走 Bifrost gateway；见 [bifrost-integration](bifrost-integration.md)。


- 在线 Demo：<https://yai-scout.onrender.com/freshness>
- 证据检查器：<https://yai-scout.onrender.com/inspector>
- 主仓库：[Gi-Tuu/yai-scout](https://github.com/Gi-Tuu/yai-scout)

## 1. 问题

LLM/Agent 的答案经常“看起来有引用”，但引用的是旧页面。  
Grounding / citation check 只能回答“是否被证据支持”，不能回答“证据是否过期、当前值是什么”。

## 2. 两种技术怎么配合

| 技术 | 作用 |
|---|---|
| **Tavily** | live research：找当前来源、抓内容、来源等级/时间信号 |
| **Bifrost** | OpenAI-compatible 模型网关：claim 抽取、关系判断、修正建议；provider routing / logs / budget |
| 确定性代码 | 状态判定、预算、证据存储、评分、审计 |

## 3. 我们做什么

```text
答案 → 拆 claim → 判时间敏感性 → Tavily 取当前证据
     → 状态（FRESH/STALE/CONFLICTED/INSUFFICIENT）
     → 分数拆解 + 当前值 + 修正建议
```

差异化：

1. **Post-hoc audit**：审计任意模型已有答案，不要求换模型/重建 RAG；
2. **Support ≠ Freshness**：证据可以完全支持，但已经过期；
3. **给当前值 + 修正**，不只红绿灯；
4. **As-of replay**：同一答案在 2026-10-28 FRESH、2026-11-01 STALE。

## 4. 60 秒演示

```powershell
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py
# 或线上
.\.venv\Scripts\python.exe scripts\demo_fixed_cases.py --url https://yai-scout.onrender.com --check
```

固定用例（[benchmarks/demo/cases.json](../benchmarks/demo/cases.json)）：

| case | 预期 |
|---|---|
| Python 3.12 于 2023 发布 | FRESH（稳定事实，旧来源不误伤） |
| YAI 0.24.0，as_of 2026-10-28 | FRESH（当时正确） |
| 同一答案，as_of 2026-11-01 | STALE（citation ≠ freshness） |
| YAI 0.25.0，as_of 2026-11-01 | FRESH（当前值） |

**录制策略**：先用 `--record` 生成缓存，录屏时用默认离线回放，保证不受网络/额度影响；现场可用 `--check` 验证实时结果。Tavily 定价的 live stale 案例可另在 `/freshness` 手动跑（受搜索质量影响，不作为固定镜头）。

## 5. 关键证据

- Claim 级审计 + 证据时间 + 来源等级 + 判定理由；
- Freshness 分数：relation / recency / authority / coverage，版本化 policy；
- 规则层标注 60 条：agreement 1.000（**规则作者设计，非独立人工泛化**，见 [accuracy-eval](../docs/accuracy-eval.md)）；
- 真实 replay：GitHub Releases 官方历史，STALE 24 → FRESH 88；
- 已接入 Tavily Search/Extract；无 key 时 keyless 降级。

## 6. 运行

```powershell
uv sync --extra dev
cp .env.example .env    # TAVILY_API_KEY / OPENAI_API_KEY（可选）
uv run uvicorn yai_scout.api.app:app --port 8010
# 打开 /freshness，粘贴答案
```

或直接调用：

```bash
curl -s http://127.0.0.1:8010/freshness/verify \
  -H 'Content-Type: application/json' \
  -d '{"answer":"Tavily 免费计划每月提供 500 credits。","as_of":"2026-11-01"}'
```

## 7. 诚实局限

- 检索/抽取仍有噪声；复杂页面可能落到 INSUFFICIENT；
- 20/60 条标注不是独立人工 ground truth；
- Wayback 网页历史不可达；replay 目前覆盖 GitHub Release 类事实；
- 公开 Demo 有限流（4/min、60/日），冷启动 30–90s；
- 自动 Anchor 更新默认关闭，需人工 approve。

## 8. 为什么不是“重复造轮子”

| 类别 | 代表 | 我们不同 |
|---|---|---|
| 答案引擎 | Perplexity、Tavily Research | 审计已有答案，不生成新答案 |
| Grounding/幻觉 | Vectara HHEM、Ragas、Cleanlab | 判“是否过期”，不只“是否被支持” |
| 记忆/RAG | Zep/Graphiti、MemStrata | 不要求改造上游，可后挂审计 |
| 事实核查 | 引用验证工具 | 输出当前值 + 修正 + as-of replay |

详见 [positioning.md](positioning.md)。


