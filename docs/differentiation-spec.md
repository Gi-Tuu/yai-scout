# YAI Scout 差异化设计技术规格书（v2）

> 定位：**Freshness-aware AI Agent Benchmarking**
> 一句话：*We benchmark not just whether agents are right, but whether their evidence is still current.*
> 版本：v2.0 · 2026-11-01 · 状态：设计已定，按 P0→P1→P2 实施
> 关联：`charter-benchmark.md`（B2）、`charter-freshness.md`（T1）、`architecture-shared.md`（共享底座）

---

## 0. 先审查：哪些保留、哪些改变

| 现有设计 | 结论 |
|---|---|
| 共享底座（Adapter / Dataset / Sources / Evidence / Store / Trace / Eval） | **保留**，并扩展 Claim/Evidence/Snapshot 模型 |
| 两个独立产品 + 独立入口 + 共享代码（monorepo） | **保留**（ADR-0002） |
| 规则 + LLM claim 抽取、Tavily 核验、Freshness 分数 | **保留并升级**：增加时间敏感性、target_time、validity window、关系与新鲜度分离 |
| 6 项 Benchmark 指标 | **保留并扩展**：加入 Freshness / Evidence Quality / Claim Support / Stale Rate / 成本明细 |
| 13 题数据集 | **升级**：按 Stable / Time-sensitive / Changed / Conflicting 四类重建为 24 题 |
| 现有综合分（0–1 加权） | **降级为可选视图**；默认改为多维表 + Pareto，不再用单一不透明分数 |
| As-of 时间旅行 | **新增**：必须以真实快照实现，禁止用当前搜索伪造历史 |

---

## 1. 六项差异化能力（总览）

| # | 能力 | 解决什么问题 | 对哪个产品 | 优先级 |
|---|---|---|---|---|
| D1 | Freshness as a first-class metric | "答案对"不等于"现在还对" | B2 + T1 | **P0** |
| D2 | Claim-level evidence verification | 整段引用无法证明每句话 | T1（B2 复用） | **P0** |
| D3 | As-of temporal replay | 事实随时间变化，无法对比 | B2 + T1 演示 | P1 |
| D4 | Multi-dimensional / Pareto ranking | 单一总分掩盖成本-效果权衡 | B2 | P0（基础）/P1（Pareto） |
| D5 | Cross-architecture adapter | 只测自家 Agent 没有公平性 | B2 | **P0**（HTTP）/P1（Python/CLI） |
| D6 | Freshness benchmark dataset | 没有专门数据就无法证明指标有效 | B2 + T1 | P1（P0 用最小 12 题） |

---

## 2. D1：Freshness as a First-class Metric

**核心思想**：先把事实按时间敏感性分类，再判断证据是否覆盖目标时间；新鲜度不是"来源越新越好"，而是"对这类事实，证据是否仍在有效期内且足够权威"。

- **输入**：claim 文本 + target_time + 证据列表（来源、发布时间、更新时间、档位、关系）。
- **输出**：`temporal_sensitivity`（4 档）、`validity_window`（天）、`freshness_status`、`freshness_score`（0–100，可空）、`confidence`、`rationale`。
- **技术**：规则（类型/关键词/实体）+ LLM 分类（JSON）；评分用确定性公式（见 `spec-freshness-scoring.md`）。
- **依赖**：`scout_core/evidence`、`sources`、`dataset`。
- **测试**：10 条边界向量（稳定事实旧来源不扣分、旧价格判 stale、MENTIONS 不算支持、冲突证据判 CONFLICTED、无证据判 INSUFFICIENT…）。
- **如何证明有效**：24 题数据集上，Freshness 判定与人工标注一致率 ≥0.8；Stable 类不因来源旧被误判 ≥90%；报告展示每条证据的贡献项。

**状态枚举**：`FRESH / STALE / CONFLICTED / INSUFFICIENT / UNKNOWN`
（`UNKNOWN` 用于"该 claim 不属于可验证事实"或"无法判断"，不强行给结论。）

---

## 3. D2：Claim-level Evidence Verification

**流水线**：

```text
Answer → Claim Extraction → Temporal Sensitivity → Evidence Retrieval
→ Relation Analysis (SUPPORTS/CONTRADICTS/MENTIONS/INSUFFICIENT)
→ Freshness Evaluation → Verification Report → Evidence Inspector
```

**关键要求**：
- 每条 claim 独立可追溯：claim_id、原文、时间敏感性、target_time、证据 URL、来源名、published_at、updated_at、retrieved_at、relation、freshness_status、confidence。
- **关系 ≠ 新鲜度**：2024 年官方公告可以 SUPPORTS 一个历史事实，但不能证明该价格在 2026 年仍有效。
- 证据不足必须返回 `INSUFFICIENT`，不能默认"没问题"。
- Evidence Inspector：点 claim → 原文、原答案引用、实时证据、时间戳、关系、变化、判定理由、分数拆解。

**输入/输出**：见 `spec-freshness-scoring.md` 的数据模型与 `spec-benchmark-adapter.md` 的引用字段。
**测试**：每条 claim 至少一个证据或显式 INSUFFICIENT；关系判定与人工标注一致率 ≥0.8（20 条标注）。

---

## 4. D3：As-of Temporal Replay

**目标**：同一问题在两个时间快照下对比，展示"事实变化 / 证据失效 / Agent 是否发现变化"。

**硬约束**：
- Tavily 不能还原历史互联网；`as_of=2025-06` 不是历史搜索。
- 历史证据必须来自**当时真实保存的快照**（Wayback Machine CDX / 手动存档），否则只能标 `simulated`，不得伪装成真实历史。
- 运行不可变：`config_hash + dataset_version + snapshot_ids + code_commit + result_hash` 落库，不允许回写。

**技术**：
1. `EvidenceSnapshot` 表（URL、content_hash、raw_path、published_at、fetched_at、source_type、snapshot_origin）。
2. `ImmutableRun`（run 创建后只追加结果，不允许 UPDATE 关键字段）。
3. `TemporalComparisonEngine`：按 claim key 对齐两次 run → stable / changed / new / removed；输出 drift 报告。
4. Demo 数据：优先用 Wayback 真实存档（如 YAI release 页 v0.24→v0.25、Tavily 定价页历史版本）；无存档的题目标 `simulated` 并说明。

**验收**：任意 replay 结果都能回答"证据来自哪个快照、何时抓取、为什么可用"；无快照的历史题不得输出"已核验"。

详见 `spec-temporal-replay.md`。

---

## 5. D4：Multi-dimensional / Pareto Ranking

**指标**（全部可追溯）：

| 维度 | 指标 | 方向 |
|---|---|---|
| 正确性 | Accuracy（金标命中率） | ↑ |
| 事实可靠性 | Freshness（claim 均分）、Stale Claim Rate | ↑ / ↓ |
| 证据质量 | Evidence Quality（引用覆盖率 × 关系支持 × 来源档位） | ↑ |
| 任务能力 | Completion Rate | ↑ |
| 经济性 | Tokens（输入/输出分开）、Estimated Cost（带价格表版本） | ↓ |
| 效率 | Latency（p50/p95） | ↓ |
| 稳定性 | Failure Rate | ↓ |

**排名**：
- 默认：**多维表**，任意列可排序；不默认展示一个综合分。
- Pareto：目标设为（Accuracy↑、Freshness↑、Cost↓、Latency↓）；非支配排序，展示 frontier。
- 可选综合分：权重显式展示、可切换，标注"weighted view, not ground truth"。

**成本**：保留原始 token（in/out）、provider、model、price_table_version、effective_date；缺失价格标 `estimated=true`；不把 credits 与美元混算。

详见 `spec-benchmark-adapter.md`。

---

## 6. D5：Cross-architecture Agent Adapter

**协议（HTTP，P0）**：

```text
GET  /manifest        → {agent_id, agent_version, framework, models[], tools[], capabilities[]}
POST /run             → {protocol_version, task:{id,question,target_time}, execution:{deadline_s,max_tokens,tools_allowed}, eval:{...}}
                       ← {answer, citations[], evidence_refs[], trace[], usage:{prompt_tokens,completion_tokens,model,provider},
                          cost:{estimated_usd,currency,price_table_version,estimated}, latency_ms, error}
```

**接入方式**：
1. HTTP JSON（P0，外部 Agent 直接实现或包一层）；
2. Python SDK（P1，`ScoutAgent.answer(task)` 基类）；
3. CLI Wrapper（P1，stdin JSON → stdout JSON）。

**公平性**：同 task、同 target_time、同工具权限、同超时/预算、同验收；记录每个 Agent 的模型与工具配置，报告中展示差异（避免把配置优势当成架构优势）。
**不承诺**"零改代码接入"——外部 Agent 可能需要一个 adapter/wrapper，文档写清。

**验收**：至少接 1 个非 YAI、非 Python 的外部 Agent（HTTP 或 CLI）；协议文档 + curl 示例 + 外部 Agent demo。

---

## 7. D6：Freshness Benchmark Dataset

四类（每类最小题数）：

| 类别 | 目的 | 题数（P0/P1） |
|---|---|---|
| A. Stable Facts | 验证"来源旧 ≠ 过时"（数学/历史日期/定理） | 3 / 6 |
| B. Time-sensitive | 价格、版本、人员、法规、产品功能 | 4 / 8 |
| C. Changed Facts | 已知变化（旧值→新值），测 Agent 是否识别旧信息 | 3 / 6 |
| D. Conflicting Evidence | 来源互相矛盾，测冲突处理 | 2 / 4 |

每条：test_id、category、question、target_time、expected_claims[]、reference_evidence[]（含 snapshot_id）、validity_window、expected_relation、evaluation_criteria、version、reviewer、changelog。
**可版本化、可重复、来源可追溯、保留快照、支持人工审核；不得用未核实的生成数据当权威。**

详见 `spec-benchmark-adapter.md` 与 `benchmarks/` 规划。

---

## 8. Claim / Evidence 数据模型（共享）

```text
Claim:
  claim_id, answer_id/run_id, claim_text, claim_type,
  temporal_sensitivity ∈ {STABLE, SLOW, SENSITIVE, VOLATILE},
  target_time, validity_window_days, numbers[], time_scope,
  extractor, extractor_confidence

Evidence:
  evidence_id, claim_id, url, canonical_url, source_name, domain, tier,
  published_at, updated_at, retrieved_at, snapshot_id, quote, quote_start/end,
  content_hash, relation ∈ {SUPPORTS, CONTRADICTS, MENTIONS, INSUFFICIENT},
  relation_confidence, relation_reason

FreshnessVerdict:
  claim_id, status ∈ {FRESH, STALE, CONFLICTED, INSUFFICIENT, UNKNOWN},
  score(0–100|null), confidence, rationale,
  score_breakdown{relation, recency, authority, coverage},
  suggestion

Run / Snapshot:
  run_id, app, task_id, agent_id, config_hash, dataset_version,
  snapshot_ids[], code_commit, started_at, finished_at, immutable
  snapshot_id, url, content_hash, raw_path, published_at, fetched_at, origin
```

**关系语义**：
- SUPPORTS：来源明确给出与 claim 一致的值/事实；
- CONTRADICTS：来源给出不同的值/事实（同单位/同实体），且时间上可用于判断；
- MENTIONS：提到主题但不足以支持或反驳；
- INSUFFICIENT：没有可用证据。

---

## 9. 时间敏感性分类（规则 + LLM，可解释）

| 类别 | 典型对象 | 默认 validity window | 规则信号 |
|---|---|---|---|
| STABLE | 数学定理、物理常数、历史事件日期、已故人物生平 | 3650 天 | 无"当前/最新/目前"；含历史年份且事件已结束；数学/定义类 |
| SLOW | 公司成立时间、长期法规框架、组织架构 | 730 天 | 法律/组织类且无"修订/最新" |
| SENSITIVE | API 价格、软件版本、产品功能、政策细则 | 180 天 | 价格/版本/定价/套餐/功能 |
| VOLATILE | 实时排名、股价、当前人数、"latest" 榜单 | 30 天 | "当前/最新/现在/排名/股价/用户数" |

> 说明：窗口是**先验**（按事实变化频率），不是"来源新旧"；会在数据集中按类别校准并版本化（`ts_policy_version`）。LLM 只做分类，不许改分数。

---

## 10. Freshness Score（初版公式，可校准）

对 claim 的可用证据集 E：

```text
relation_score = Σ_{e∈E} w_rel(e) * w_tier(e)
  w_rel: SUPPORTS +1, CONTRADICTS -1, MENTIONS 0, INSUFFICIENT 0
  w_tier: T1 1.0, T2 0.8, T3 0.5, T4 0.25

recency_score(e) = 1,                          if sensitivity = STABLE
                 = clamp(1 - age(e)/H(C), 0, 1), otherwise
  age(e) = target_time - effective_date(e)（effective_date = updated_at or published_at）

authority_score = max(w_tier(e) for e with relation ∈ {SUPPORTS, CONTRADICTS})
coverage_score  = 1 if 存在 relation ≠ MENTIONS 的证据且 effective_date 可判定，否则 0

score = 100 * clamp(0.5*norm(relation_score) + 0.3*recency_score + 0.2*authority_score, 0, 1)
        （coverage=0 时 score=null，status=INSUFFICIENT）
```

**状态判定（先于分数）**：

| 条件 | 状态 |
|---|---|
| 无证据 / 只有 MENTIONS | INSUFFICIENT（score=null） |
| 存在权威 CONTRADICTS 且在有效窗内 | STALE |
| 权威 SUPPORTS 且无权威 CONTRADICTS | FRESH |
| 权威 SUPPORTS 与权威 CONTRADICTS 并存 | CONFLICTED |
| 只有非权威 SUPPORTS（T3/T4） | INSUFFICIENT（低权威） |
| 只有过期 SUPPORTS（超出 H）且类别为 SENSITIVE/VOLATILE | STALE（outdated） |
| 无法归类/非事实 | UNKNOWN |

**权重校准**：初始权重为 rubric；用 60 条人工标注 claim 做网格搜索，报告 MAE/AUC，并把最优权重版本化（`freshness_weights_version`）。没有校准前不得宣称"最优"。

**边界规则**（对应任务书 §6）：
1. 来源旧 ≠ 过时：STABLE/SLOW 不因 age 扣分；
2. 来源新 ≠ 可信：T3/T4 单源不能判 FRESH；
3. MENTIONS ≠ SUPPORTS；
4. CONTRADICTS 要看时间窗与上下文；
5. 无证据 = INSUFFICIENT，不是 stale；
6. 检索不全会标 coverage/INSUFFICIENT，不假装覆盖；
7. 不同 Agent 条件必须可比较（记录模型/工具/预算）；
8. 历史快照不能伪造；
9. 分数必须给 breakdown；
10. 成本必须标 estimated。

---

## 11. P0 / P1 / P2 功能拆分

### P0（必须，11/08 前）

| 模块 | 验收 |
|---|---|
| HTTP Adapter 协议 + manifest | 外部 Agent 可接；curl 示例通过 |
| Benchmark Runner（12 题 × 3 Agent，P0 最小集） | 结果落库、可复跑 |
| Claim Extraction（LLM + 规则） | 20 条标注集覆盖 ≥80% |
| Tavily 检索 + 关系判定 | 每条 claim 有证据或 INSUFFICIENT |
| Freshness Score（初版公式） | 10 条边界测试；breakdown 可见 |
| 多维排行榜（Accuracy/Freshness/Stale/成本/时延） | 可排序、可下钻 |
| 两个独立入口 `/benchmark` `/freshness` | 各自可独立启动 |

### P1（尽量，11/12 前）

Evidence Inspector、Freshness Dataset 24 题、Pareto Frontier、历史快照、答案漂移、外部 Agent demo。

### P2（有余力）

完整时间旅行可视化、更多 Adapter（LangChain/CrewAI 等）、大规模数据集、高级统计、多轮对比。

---

## 12. 模块级验收标准（输入/输出/技术/依赖/测试/证明）

| 模块 | 输入 | 输出 | 技术 | 依赖 | 测试 | 证明 |
|---|---|---|---|---|---|---|
| TS Classifier | claim + target_time | 4 档类别 + 窗口 + 理由 | 规则 + LLM JSON | evidence | 20 条人工标注，一致率 ≥0.8 | Inspector 展示类别与理由 |
| Claim Extractor | answer | claims[] | LLM JSON + 子串校验 + 规则兜底 | llm | 20 条标注覆盖 ≥80% | 抽取列表可点开原文 |
| Evidence Retriever | claim | evidence[] | Tavily search/extract + 去重 + 档位 | sources | 每条 claim ≥1 次检索 | 证据带 URL/时间/档位 |
| Relation Judge | claim + evidence | relation + confidence | 数字规则 + LLM 复核 | evidence | 20 条标注 ≥0.8 | Inspector 显示关系与理由 |
| Freshness Scorer | claim + evidence + policy | status + score + breakdown | 决策表 + 公式 | ts_policy | 10 条边界 + 单调性测试 | 分数拆解可见 |
| Adapter | task | answer + usage + trace | HTTP/JSON Schema | contracts | 外部 Agent E2E | `/benchmark` 现场接入 |
| Runner | agents × tasks | runs + results | asyncio + 超时/重试/预算 | store/trace | 可复跑、config_hash | 两次 run 对比 |
| Pareto | results | frontier | 非支配排序 | eval | 3 Agent 支配关系测试 | 散点图 + 表 |
| Replay | two runs/snapshots | drift report | snapshot + diff | store | 快照可追溯 | 时间对比页 |
| Inspector | claim_id | 证据链页面 | 前端 + API | store | 每条 claim 可追溯 | 评委可现场点 |

---

## 13. 比赛 Demo 设计

### T1（2 分钟）

1. 粘贴一段"看起来正常"的答案（含旧价格/旧版本/一个稳定事实）。
2. Claim 列表 + 时间敏感性标签 + 逐条证据。
3. 点一条 stale：原文、官方现值、来源时间、判定理由、分数拆解、修正建议。
4. 点一条 stable：来源较旧但判 FRESH——证明"来源旧 ≠ 过时"。
5. （P1）As-of 对比：同一答案在 2025-06 / 2026-11 的差异。

### B2（2 分钟）

1. 同一研究任务，三个不同架构 Agent（HTTP 外部 / Python / CLI）一键接入。
2. 多维表：Accuracy / Freshness / Stale Rate / 成本 / 时延。
3. Pareto：准确率-成本 frontier，指出"更便宜但更新鲜"的组合。
4. 点开一个 bad case：Agent 答案对但引用 2024 数据 → Freshness 低。
5. 可复现：config_hash + 重跑。

### 统一入口（30 秒）

`/` 两个卡片 → `/benchmark`、`/freshness`；强调两个独立作品、共享底座。

---

## 14. 现状差距（截至 2026-11-01）

| 能力 | 现状 | 差距 |
|---|---|---|
| Claim 抽取 | LLM + 规则已实现 | 缺 target_time/时间敏感性分类 |
| 证据核验 | Tavily + 关系 + LLM 复核 | 缺 INSUFFICIENT 显式、updated_at、snapshot_id |
| Freshness | 规则分 + 权威性门槛 | 缺 4 档敏感性、窗口、confidence、breakdown、CONFLICTED |
| Benchmark | 13 题 + 榜单 | 缺 4 类数据集、claim-level eval、Pareto、成本明细 |
| Adapter | mock/检索/LLM，HTTP 类未实测 | 缺协议文档、manifest、外部 Agent demo |
| As-of | 无 | 全新（P1） |
| 独立入口 | `/detector` + `/bench` | 需改为 `/freshness` + `/benchmark` 并独立启动 |
| 测试 | 46 tests | 需补时间敏感性、决策表、Pareto、Adapter 协议测试 |

> 结论：现有代码保留约 60–70%（store/sources/LLM/抽取/检索/评分骨架），P0 的重点是"补语义 + 补协议 + 补数据集"，不是推倒重来。
