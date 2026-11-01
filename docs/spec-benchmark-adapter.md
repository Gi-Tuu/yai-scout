# 规格：Agent Adapter 协议、Benchmark Dataset、指标与 Pareto（B2 / D4 / D5 / D6）

> 版本 v2.0 · 2026-11-01
> 协议版本：`scout-adapter/1.0`；数据集版本：`freshness-bench/0.1`

## 1. Agent Adapter 协议（HTTP，P0）

### 1.1 Manifest（发现能力）

```http
GET /manifest
```

```json
{
  "protocol_version": "scout-adapter/1.0",
  "agent_id": "my-agent",
  "agent_version": "0.3.1",
  "framework": "langgraph | crewai | custom | yai",
  "models": [{"provider": "deepseek", "model": "deepseek-v4.1-flash"}],
  "tools": ["web_search", "read_url"],
  "capabilities": {"streaming": false, "claims": true, "trace": true},
  "contact": "team@example.com"
}
```

### 1.2 Run（执行一次任务）

```http
POST /run
Content-Type: application/json
```

```json
{
  "protocol_version": "scout-adapter/1.0",
  "run_id": "run_123",
  "task": {
    "task_id": "b2_b_pricing_01",
    "question": "Tavily 免费计划每月包含多少 API credits？",
    "target_time": "2026-11-01",
    "category": "time_sensitive"
  },
  "execution": {
    "deadline_s": 120,
    "max_tokens": 4000,
    "tools_allowed": ["web_search", "read_url"],
    "budget_usd": 0.05
  },
  "eval": {"require_citations": true}
}
```

响应：

```json
{
  "protocol_version": "scout-adapter/1.0",
  "answer": "每月 1,000 credits [1]。",
  "citations": ["https://docs.tavily.com/documentation/api-credits"],
  "claims": [
    {"text": "免费计划每月 1,000 credits", "type": "pricing",
     "support": ["https://docs.tavily.com/documentation/api-credits"]}
  ],
  "usage": {"prompt_tokens": 1200, "completion_tokens": 120,
            "model": "deepseek-v4.1-flash", "provider": "deepseek"},
  "cost": {"estimated_usd": 0.0005, "currency": "USD",
           "price_table_version": "2026-11-01", "estimated": true},
  "latency_ms": 2400,
  "trace": [{"step": "search", "query": "...", "ms": 900}],
  "error": null
}
```

### 1.3 错误与超时

| HTTP | 含义 | Runner 行为 |
|---|---|---|
| 200 | 成功 | 评分 |
| 4xx | 请求错误（Agent 侧） | 记 failure，不重试 |
| 5xx / 超时 | Agent 故障 | 重试 1 次，仍失败记 failure |
| 响应 schema 不合法 | 协议错误 | 记 failure + 原因 |

### 1.4 Python SDK（P1）

```python
from scout_core.adapters import ScoutAgent, Task, AgentResponse

class MyAgent(ScoutAgent):
    agent_id = "my-agent"
    async def answer(self, task: Task) -> AgentResponse:
        return AgentResponse(answer="...", citations=[...], usage=...)
```

### 1.5 CLI Wrapper（P1）

```bash
scout-adapter serve --agent my_agent:MyAgent --port 9100
# stdin:  task JSON；stdout: response JSON（供非 Python Agent 包装）
```

### 1.6 公平性契约（必须记录）

- 同 `task`、同 `target_time`、同 `tools_allowed`、同 `deadline_s`、同 `budget_usd`；
- 记录每个 Agent 的 `models`、`tools`、`framework`、版本；
- 报告展示配置差异，避免把"用了更强模型"当成"架构更好"；
- 不允许 Runner 给某个 Agent 额外提示或额外检索轮次。

> **不承诺**"零代码接入"：外部 Agent 通常需要一个 HTTP/CLI adapter（约 30–80 行）；文档明确写。

## 2. Benchmark Dataset（D6）

### 2.1 四类与最小题数

| 类别 | 目的 | P0 | P1 |
|---|---|---|---|
| A. Stable | 来源旧 ≠ 过时 | 3 | 6 |
| B. Time-sensitive | 价格/版本/人员/法规/功能 | 4 | 8 |
| C. Changed | 已知旧值→新值 | 3 | 6 |
| D. Conflicting | 来源互相矛盾 | 2 | 4 |
| **合计** | | **12** | **24** |

### 2.2 数据条目 schema

```json
{
  "test_id": "b2_b_pricing_01",
  "version": "freshness-bench/0.1",
  "category": "time_sensitive",
  "question": "Tavily 免费计划每月包含多少 API credits？",
  "target_time": "2026-11-01",
  "expected_claims": [
    {"text": "Tavily 免费计划每月 1,000 credits", "claim_type": "pricing",
     "temporal_sensitivity": "SENSITIVE", "validity_window_days": 180,
     "expected_relation": "SUPPORTS", "gold_values": ["1000"]}
  ],
  "reference_evidence": [
    {"url": "https://docs.tavily.com/documentation/api-credits",
     "snapshot_id": "snap_20261101_tavily_credits",
     "published_at": "2026-10-28", "tier": 1, "relation": "SUPPORTS"}
  ],
  "validity_window_days": 180,
  "expected_freshness": "FRESH",
  "evaluation_criteria": ["correctness", "freshness", "evidence"],
  "reviewer": "hangzhou",
  "changelog": "v0.1 初始"
}
```

### 2.3 版本与污染控制

- 数据集版本化（semver）；每次变更写 changelog；
- 12/24 题公开，另留 3 题隐藏（提交前不发布）；
- `target_time` 必须早于/等于证据可用时间；历史题必须带 snapshot_id；
- 来源必须可访问、可存档；不接受未核实的生成数据；
- 人工审核：每题 ≥1 人复核，记录 reviewer。

## 3. 指标定义

| 指标 | 公式 | 说明 |
|---|---|---|
| Accuracy | 命中金标数 / 金标总数（数字容差按单位） | 0–1 |
| Completion | 非空且非拒答 / 总任务 | 0–1 |
| Freshness | 时间敏感 claim 的 freshness 均分 / 100 | 仅 SENSITIVE/VOLATILE |
| Stable-Fact Integrity | STABLE claim 判 FRESH 的比例 | 检验"旧来源不误伤" |
| Stale Claim Rate | STALE claim 数 / 时间敏感 claim 数 | 越低越好 |
| Evidence Quality | citation_coverage × (0.6×supported_ratio + 0.4×authority) | 见下 |
| Claim Support | 有 ≥1 SUPPORTS 的 claim / 有证据的 claim | 0–1 |
| Token In/Out | 原始计数，分开记录 | 不合并 |
| Cost (est.) | in/1e6×price_in + out/1e6×price_out | 带 price_table_version |
| Latency | p50 / p95 | 毫秒 |
| Failure Rate | failure / 总任务 | 0–1 |

```text
citation_coverage = 有 ≥1 证据的 claim / claim 总数
supported_ratio  = 有 SUPPORTS 的 claim / 有证据的 claim
authority        = mean(w_tier of supporting evidence)
w_tier: T1 1.0, T2 0.8, T3 0.5, T4 0.25
```

## 4. 成本模型（可追溯，不混算）

`pricing/price_tables/2026-11-01.json`：

```json
{
  "version": "2026-11-01",
  "effective_date": "2026-11-01",
  "currency": "USD",
  "models": [
    {"provider": "deepseek", "model": "deepseek-v4.1-flash",
     "input_per_m": 0.30, "output_per_m": 1.20, "source": "https://api-docs.deepseek.com/..."}
  ]
}
```

- 记录 `provider / model / pricing_version`；缺价格 → `estimated: true` 且 `cost: null`（不猜）。
- Tavily credits 单独记（credits 数 + 折算参考），**不与 token 成本合并**。
- 报告展示"原始 token + 单价表 + 估算公式"。

## 5. 多维排名与 Pareto（D4）

### 5.1 默认展示

多维表（不做单一综合分）：Agent | Accuracy ↑ | Freshness ↑ | Stale ↓ | Evidence ↑ | Cost ↓ | Latency ↓ | Failure ↓。
列可排序；点 Agent 看逐题明细。

### 5.2 Pareto

目标向量（越小越好统一为成本/延迟/陈旧率，越大越好为准确率/新鲜度）：

```text
objectives = [Accuracy↑, Freshness↑, -Cost, -Latency, -StaleRate]
A dominates B ⇔ 所有目标不差，且至少一个更好
frontier = 非支配集（O(n²)，n<20 足够）
```

UI：散点图（Accuracy vs Cost，点大小=Freshness），frontier 连线；表内标注 "Pareto" 徽章。
可选综合分：权重显式展示（如 0.4 accuracy + 0.2 freshness + 0.2 cost + 0.1 latency + 0.1 stale），并标注 "weighted view, configurable"。

### 5.3 可复现

`config_hash = sha256(agent_specs + task_ids + dataset_version + target_time + budget + code_commit)`；报告记录；同 hash 重跑结果一致（确定性 Agent ±0.02）。

## 6. 验收标准

- [ ] 3 个不同架构 Agent 通过 HTTP/CLI/Python 接入（其中 ≥1 外部进程）
- [ ] 12 题（P0）/24 题（P1）数据集，四类齐全，含 hidden split
- [ ] 6 项核心指标 + token in/out + 成本明细全部展示
- [ ] Pareto frontier 计算正确（3 Agent 单测）
- [ ] 同 config 重跑一致
- [ ] 报告可导出（JSON + Markdown）
- [ ] 外部 Agent 接入文档 + curl 示例 + demo
