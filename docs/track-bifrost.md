# YAI Scout Benchmark — Evaluation Evidence (Supporting, Not Primary)

> **这不是本次提交的 primary challenge。**  
> 本仓库唯一 primary submission 是 Tavily Track Problem 05（Stale-answer detector）。  
> Benchmark 作为 freshness 的评测证据保留，**不声称完成 Bifrost Track Problem 02**；  
> 若要报 02，还需 failure injection、重复运行、steps/tool calls 逐步 trace。

> **Agent Benchmarking Platform**：不只看模型分数，而是比较不同 Agent 架构在**准确率、新鲜度、证据质量、成本、延迟**上的取舍。

- 在线 Demo：<https://yai-scout.onrender.com/benchmark>
- 主仓库：[Gi-Tuu/yai-scout](https://github.com/Gi-Tuu/yai-scout)

## 1. 问题

模型 benchmark 很多，但 Agent 是“模型 + 工具 + 检索 + 架构”的组合。  
同一模型换一个 Agent 架构，准确率、证据质量、成本和延迟都会变；只测模型无法回答“该选哪个 Agent 架构”。

## 2. 我们做什么

```text
同一批任务 + 同一个 target_time + 同一预算
  → 不同架构 Agent（HTTP / Python / CLI / LLM RAG / 检索基线）
  → 多维结果
  → 排行榜 + Pareto frontier
  → 可复现 manifest + result_hash
```

## 3. 评测设计

- **数据集**：24 题（21 公开 + 3 隐藏/compromised），四类：
  `stable / time_sensitive / changed / conflicting`；
- **Adapter 协议**：`scout-adapter/1.0`（`GET /manifest` + `POST /run`），外部 Agent 可接入；
- **指标**：
  - Accuracy（金标匹配）
  - Freshness / Stale rate / Evidence quality / Claim coverage
  - Cost、Latency、Tokens in/out
- **排名**：多维度表 + **Pareto frontier**（不强行合成一个黑箱分）；
- **复现**：Experiment Manifest（dataset hash、agent manifest、模型/工具/预算、evaluator/policy/weights 版本、code commit、lock hash、snapshot IDs）+ `config_hash` + `result_hash` + `/verify`。

## 4. 30 秒演示

```powershell
# 启动服务
uv run uvicorn yai_scout.api.app:app --port 8010

# 2 个 Agent × 3 题
curl -s http://127.0.0.1:8010/benchmark/runs \
  -H 'Content-Type: application/json' \
  -d '{"agent_ids":["mock_good","llm_agent"],"task_ids":["b_tavily_free_credits","b_deepseek_flash_price","a_stable_python_release"]}'
```

页面 `/benchmark` 选择 Agent 与题目 → 跑 → 看多维榜单和 Pareto。

跨架构接入：

```bash
# HTTP 外部 Agent 示例
python examples/echo_agent.py   # :9101
HTTP_AGENT_URL=http://127.0.0.1:9101 uv run uvicorn yai_scout.api.app:app --port 8010
```

## 5. 关键证据

- 24 题四类数据集，金标可核验；
- 3 类 Adapter（HTTP / Python / CLI）+ 内置 LLM/检索/合成基线；
- 每次 run 保存 manifest 与 `config_hash`；完成后写 `result_hash`，`GET /benchmark/runs/{id}/verify` 可重算；
- 完成后不可变，修订用 `supersedes`；
- 隐藏题不通过公开 API 暴露/执行（已标记 compromised，不宣称保密）；
- 127+ tests，CI 覆盖 3.11/3.12 + Docker。

## 6. 诚实局限

- 24 题是 demo 规模，不是学术 leaderboard；
- 隐藏题历史已公开，不能当保密数据；
- 真实 Agent 的延迟/成本有波动，`result_hash` 是结果摘要而非完整证据图；
- 外部 Adapter 需要自己实现协议，不能“零代码接入”；
- 部分运行依赖 Tavily/LLM key。

## 7. 为什么不是“又一个模型榜单”

| 常见做法 | 我们不同 |
|---|---|
| 只测模型 | 测 Agent 架构 + 工具 + 检索 |
| 单一分数 | 多维指标 + Pareto |
| 不明配置 | manifest + hash + verify |
| 不可复现 | 固定 dataset/target_time/budget + 历史 run |

详见 [spec-benchmark-adapter.md](spec-benchmark-adapter.md)、[differentiation-spec.md](differentiation-spec.md)。

