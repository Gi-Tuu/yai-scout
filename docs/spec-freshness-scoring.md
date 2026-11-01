# 规格：时间敏感性分类与 Freshness Score（T1 / D1 / D2）

> 版本 v2.0 · 2026-11-01 · 实现模块：`scout_core/evidence` + `apps/freshness`
> 目标：可解释、可测试、可校准；不使用无依据权重、不把"来源新"当"可信"。

## 1. 输入与输出

**输入**：`Claim{text, claim_type, numbers[], target_time}` + `Evidence[]`（url、domain、tier、published_at、updated_at、retrieved_at、relation、relation_confidence、quote）。
**输出**：`FreshnessVerdict{temporal_sensitivity, validity_window_days, status, score(0–100|null), confidence, rationale, score_breakdown, suggestion}`。

## 2. 时间敏感性分类（Temporal Sensitivity Classification）

### 2.1 四档定义与默认有效期窗口

| 档位 | 含义 | 示例 | 默认窗口 H | 规则信号（优先级从高到低） |
|---|---|---|---|---|
| `STABLE` | 不随现实时间改变的事实 | 数学定理、物理常数、历史事件日期、已故人物 | 3650 天 | 数学/定义/定理；含历史年份且事件已结束；无"当前/最新/目前/截至" |
| `SLOW` | 年际变化 | 公司成立时间、长期法规框架、组织架构、长期统计口径 | 730 天 | 法规/组织/成立/架构；无修订/最新限定 |
| `SENSITIVE` | 季度/半年变化 | API 价格、软件版本、产品功能、套餐、政策细则 | 180 天 | 价格/定价/套餐/版本/功能/发布 |
| `VOLATILE` | 天/周变化 | 实时排名、股价、当前人数、"latest" 榜单 | 30 天 | 当前/最新/现在/排名/股价/用户数/市值 |

**分类算法**（规则优先，LLM 兜底，输出必须带 `reasons`）：
1. 类型信号：`claim_type == pricing/version → SENSITIVE`；`law → SLOW`（若含"修订/最新/生效"→ SENSITIVE）；`leadership → SLOW`；`date` 且指向过去 → STABLE；`statistic` 默认 SENSITIVE。
2. 时间限定词：含"当前/最新/目前/now/latest/current" → 至少 SENSITIVE，含"排名/股价/市值" → VOLATILE。
3. 稳定信号：数学/定理/常数/历史事件且无时间限定 → STABLE。
4. 规则无法判定 → LLM 分类（JSON：`{sensitivity, reasons}`），仍失败 → `SENSITIVE`（保守：宁可多验，不可漏验）。
5. **LLM 只能分类，不能改分数。**

**策略版本**：`ts_policy_version = "2026-11-01"`；窗口与信号表单独文件化，改动需升版本并重跑测试。

### 2.2 target_time 与证据时间

- `target_time`：该 claim 需要被验证的时点（默认题目 as_of；历史回放时为历史时点）。
- `effective_date(e) = updated_at or published_at`（来源声明的内容时间）。
- `age(e) = target_time - effective_date(e)`（按天，负数表示来源晚于目标时间——当前核验允许，历史回放不允许）。
- **历史回放约束**：`effective_date(e) > target_time` 的证据不可用（防未来信息泄漏）。

## 3. 证据关系（Relation）

| 关系 | 判定 | 说明 |
|---|---|---|
| `SUPPORTS` | 同实体/同单位，值一致或语义一致 | 必须有明确表述，不能靠"相关" |
| `CONTRADICTS` | 同实体/同单位，值不同，或极性相反 | 需要时间上可用于判断（见 §4） |
| `MENTIONS` | 提到主题但不足以判定 | 不计入支持/反对 |
| `INSUFFICIENT` | 没有可用证据 | 不是"正确"，也不是"错误" |

**规则优先**：数字型 claim 做值比较（容差按单位：价格 ±0.5%、版本精确、日期 ±1 天）；非数字型（法规/人事/日期）由 LLM 复核，必须返回理由。
**禁止**：MENTIONS 计入支持；把"没搜到"当成 stale。

## 4. 状态判定（决策表，先于评分）

设 `E_eff` = 关系 ∈ {SUPPORTS, CONTRADICTS} 的证据；`auth` = tier ≤ 2；`valid(e)` = `0 ≤ age(e) ≤ H`（历史回放还要求 age ≥ 0）。

| # | 条件 | 状态 | 说明 |
|---|---|---|---|
| 1 | 无证据，或仅 MENTIONS | `INSUFFICIENT` | score=null |
| 2 | 存在 auth CONTRADICTS 且 valid | `STALE` | 权威来源在有效期内给出不同值 |
| 3 | 存在 auth SUPPORTS 且无 auth CONTRADICTS，且（STABLE/SLOW 或有 valid SUPPORTS） | `FRESH` | 权威支持 |
| 4 | auth SUPPORTS 与 auth CONTRADICTS 并存（均 valid） | `CONFLICTED` | 并列展示，不给单一结论 |
| 5 | 只有非权威 SUPPORTS（T3/T4） | `INSUFFICIENT` | 低权威不足以判 fresh |
| 6 | 只有过期 SUPPORTS（超出 H），且类别为 SENSITIVE/VOLATILE | `STALE` | 证据早于有效期（outdated） |
| 7 | 只有过期 SUPPORTS（STABLE/SLOW） | `FRESH` | 稳定事实不因来源旧扣分 |
| 8 | claim 不可验证/非事实 | `UNKNOWN` | 不做判断 |

> 规则 4 与规则 2 的优先级：先检查"是否存在 auth contradict → STALE"；若同时有 auth support，升级为 CONFLICTED（更诚实）。

## 5. Freshness Score（连续分，仅用于排序/展示）

```text
w_rel  = {SUPPORTS: +1, CONTRADICTS: -1, MENTIONS: 0}
w_tier = {T1: 1.0, T2: 0.8, T3: 0.5, T4: 0.25}

relation_raw = Σ w_rel(e) * w_tier(e)          （仅 E_eff）
relation_norm = clamp((relation_raw + 1) / 2, 0, 1)

recency = 1                                     if STABLE
        = clamp(1 - min_age/H, 0, 1)            otherwise
          min_age = min(age(e)) over SUPPORTS，若 age<0（当前核验）取 0

authority = max(w_tier(e)) over E_eff           （无证据 → 0）
coverage = 1 if 至少一条 E_eff 且 effective_date 可判定 else 0

score = round(100 * (0.5*relation_norm + 0.3*recency + 0.2*authority), 0)  if coverage
      = null                                                              otherwise
```

- `score_breakdown` 必须返回 `relation_norm / recency / authority / coverage` 四项及每条证据的贡献。
- 权重（0.5/0.3/0.2）是**初始 rubric**，用 60 条人工标注做网格搜索校准（目标：与人工排序 Spearman ≥0.7，MAE ≤12），权重版本化 `freshness_weights_version`。

## 6. Confidence（0–1）

```text
confidence = 0.4*authority + 0.3*evidence_count_factor + 0.3*agreement
  evidence_count_factor = min(1, n_eff/2)
  agreement = 1 - (contradict_count / max(1, n_eff))
```
`INSUFFICIENT/UNKNOWN` 时 confidence ≤0.3。

## 7. 边界情况与处理

| 情况 | 处理 |
|---|---|
| 来源很旧但事实稳定 | STABLE → FRESH；不因 age 扣分（测试向量 T1） |
| 来源很新但是 T4 博客 | 不判 FRESH → INSUFFICIENT（测试 T2） |
| 来源只是提到主题 | MENTIONS，不计分（T3） |
| 官方 2024 公告 vs 2026 价格 | 关系 SUPPORTS 历史事实，但超 H → STALE（T4） |
| 两个权威来源冲突 | CONFLICTED，并列展示（T5） |
| 没有任何来源 | INSUFFICIENT，不是 stale（T6） |
| 数字单位不同（1,000 vs 1000） | 归一后比较（T7） |
| 版本号 0.25.0 vs 0.25 | 精确匹配，不模糊（T8） |
| 历史回放遇到未来来源 | 不可用，标 coverage=0（T9） |
| 非事实（观点/预测） | UNKNOWN（T10） |

## 8. 测试向量（最小 10 条，必须进 CI）

| ID | claim | 证据 | 期望 |
|---|---|---|---|
| T1 | "Python 3.12 于 2023 年发布"（STABLE） | 2023 官方公告（T1，age 1000d） | FRESH |
| T2 | "Tavily 免费 1,000 credits"（SENSITIVE） | T4 博客（新） | INSUFFICIENT |
| T3 | "Bifrost 是 AI Gateway" | 仅提到 Bifrost 的新闻 | INSUFFICIENT |
| T4 | "Tavily 免费 500 credits"（SENSITIVE） | 官方 docs 现为 1,000（T1，新） | STALE |
| T5 | 同上 | 官方 1,000 + 官方旧文 500 | CONFLICTED |
| T6 | 同上 | 无结果 | INSUFFICIENT |
| T7 | "$0.008/credit" | "0.008 USD per credit" | SUPPORTS → FRESH |
| T8 | "版本 0.25.0" | "0.25"（不同） | CONTRADICTS → STALE |
| T9 | 历史 as_of=2025-06 的 claim | 2026 才发布的来源 | 证据不可用 → INSUFFICIENT |
| T10 | "X 将成为最大厂商"（预测） | 任何 | UNKNOWN |

## 9. 可解释性与复现

- 报告必须展示：类别与窗口、target_time、每条证据的时间/档位/关系、决策表命中行、分数 breakdown、权重版本。
- 相同输入 + 相同证据 + 相同 policy → 相同输出（确定性；LLM 只做分类/关系，不允许它改分）。
- 数据集/权重/policy 版本变化时，报告记录版本号。
