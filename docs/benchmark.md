# Benchmark & Stale-answer Detector（实现说明）

> 对应赛题：Bifrost-02（Agent Benchmarking Platform）+ Tavily-01（Stale-answer Detector）
> 当前状态：可运行的最小闭环（demo v0），规则版检测器 + 合成/检索基线；LLM 抽取与更多适配器在路线图里。

## 1. 数据集（Bifrost-02）

`benchmarks/tasks.json`：13 道 AI 开发者生态事实题，全部有官方/一手来源，适合做「新鲜度敏感」评测。

| 字段 | 含义 |
|---|---|
| `id` | 题目 id |
| `question` | 问题 |
| `category` | `pricing` / `version` / `law` / `date` / `statistic` |
| `gold_values` | 金标值（数字或字符串，用于自动评分） |
| `gold_sources` | 金标来源 URL |
| `notes` | 备注 |

覆盖：Tavily 免费额度/计价/学生计划、DeepSeek/Claude 价格、Bifrost 许可证/端口、YAI 版本、赛事截止日期、Omnidimension 免费额度。

## 2. Agent Adapter 协议

统一接口：`async answer(task: BenchmarkTask) -> AgentAnswer{text, citations, tokens, latency_s, cost_usd}`。

已实现适配器：

| id | 类型 | 说明 |
|---|---|---|
| `mock_good` | synthetic | 按金标回答（对照组） |
| `mock_stale` | synthetic | 用"旧值"回答（演示 freshness 差异） |
| `retrieval_baseline` | 真实检索 | 单次 Tavily search + 摘要拼接（无规划/无核验） |
| `scout` | 真实检索 | 2 条计划查询 + 多查询合并（YAI Scout 风格） |
| `http` | 外部 Agent | `POST {question, as_of}` → `{answer, citations, tokens}`（注册表预留） |

## 3. 运行器（BenchmarkRunner）

- 任务 × Agent 并发执行（默认并发 2，单任务超时 120s）；
- 每条答案自动跑 freshness 检测（可关，默认每答案最多 2 条 claim，控成本）；
- 结果落 SQLite（`bench_session` / `bench_result`），前端轮询展示。

## 4. 评分

综合分（0–1）：

```text
0.45 × 数字/字符串准确率
+ 0.20 × 是否带引用
+ 0.15 × (1 − 陈旧率)
+ 0.10 × 是否完成
+ 0.10 × 成本衰减（1/(1+20×USD)）
```

指标：`numeric_accuracy`、`citation_rate`、`stale_rate`、`freshness_score`、`avg_latency_s`、`avg_tokens`、`errors`。

## 5. Stale-answer Detector（Tavily-01）

链路：`答案 → 句子切分 → 规则 claim 抽取 → 逐条 Tavily 检索 → 关系判定（supports/contradicts/mentions）→ Freshness Score + 判定`。

- 抽取：只保留含价格/版本/法规/人事/日期/统计信号的句子；不切开 `0.25.0` 这类版本号。
- 核验：每条 claim 一次 search（默认 4 条结果），查询会去掉"旧资料显示"前缀与答案值，只留主题词。
- 打分：基础 50；支持 +30（近期）/ +15（历史）；矛盾 −40（近期）/ −25（历史）；一手 +10、权威二手 +5；无一年内证据 −20；clamp 0–100。
- 判定：`stale`（有矛盾且 <55）/ `fresh`（有支持且 ≥65）/ `unverifiable`（无来源）/ `uncertain`（其余）。

## 6. 接口

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/detector` | `{answer, as_of?, max_claims?}` → 检测报告 |
| GET | `/api/detector/{id}` | 取历史报告 |
| GET | `/api/benchmark/tasks` | 数据集 |
| GET | `/api/benchmark/agents` | 适配器列表 |
| POST | `/api/benchmark/run` | `{agent_ids?, task_ids?}` → session |
| GET | `/api/benchmark/sessions/{id}` | 状态 + 明细 + 榜单 |
| GET | `/api/benchmark/leaderboard?session_id=` | 榜单 |

页面：`/detector`（检测器）、`/bench`（排行榜）。

## 7. 已知限制（下一轮）

1. claim 抽取是规则版，中文/英文混排与长句会漏；接 LLM 后需保留规则兜底。
2. 关系判定只对数字型 claim 做值比较；法规/人事类目前只能 `mentions`（需 LLM 判断）。
3. 数据集只有 13 题，金标是"静态值"；真实 benchmark 需要更多题、版本化与污染控制。
4. 合成适配器只用于演示，不能当真实 Agent 排名。
5. Freshness Score 是确定性规则分，不是概率；需要在评测报告里写清口径。
