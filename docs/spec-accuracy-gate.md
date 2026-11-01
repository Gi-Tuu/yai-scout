# Accuracy Gate + Controlled Memory Update（设计 v0）

> 日期：2026-11-01 · 状态：**设计 + 标注集，未实现代码**。  
> 边界：Freshness 回答“是否过期”；Accuracy 回答“新值是否正确”；Gate 决定“是否允许写回记忆”。  
> 目标：交付前上线“候选 → 门禁 → 受控自动更新”，默认关闭自动更新。

## 1. 为什么必须单独设计

Anchor 更新链路最容易犯的错：**把“来源变了”当成“事实正确”**。

- 来源可能是错的、过时的、转载的、营销的；
- 同一来源可能有多个镜像；
- 新值可能与旧值只是格式不同；
- 自动覆盖会污染记忆，且难以回滚。

因此：

```text
Observation → Candidate → Accuracy Gate → active Anchor + memory update
```

**Gate 通过才写；不通过只保留 candidate；永不静默覆盖旧 Anchor。**

## 2. 术语

| 术语 | 定义 |
|---|---|
| Anchor | 上次核验的来源、值、时间、hash |
| Observation | 本次从某来源看到的值/内容 |
| Candidate | 与 anchor 不同的候选值（未生效） |
| Accuracy Gate | 判断候选值是否足够可信、可自动写回的规则集 |
| Auto Update | Gate 全通过且 feature flag 开启时，追加新 Anchor 并更新记忆 |
| Review | 需要人工/评审确认 |
| Reject | 不采用该候选（无权威证据/更旧/单位不明/仅低权威） |
| No Change | 归一化后与当前值相同，不产生更新 |

## 3. 数据模型（提案）

```text
Anchor:
  id, claim_key, url, source_tier, value, content_hash,
  published_at, last_verified_at, valid_from,
  supersedes, temporal_sensitivity, status

AnchorObservation:
  id, anchor_id, url, source_tier, independent_group,
  value, normalized_value, content_hash,
  published_at, observed_at, status

AnchorCandidate:
  id, anchor_id, claim_key, old_value, new_value,
  normalized_old, normalized_new,
  evidence: [observation_id],
  gate_decision: auto_update | review | reject | no_change,
  gate_reason, gate_version, confidence,
  accuracy_status: pending | approved | rejected,
  created_at, decided_at, decided_by
```

## 4. 归一化规则（先于 Gate）

| 类型 | 规则 | 不确定时 |
|---|---|---|
| 数字/金额 | 去千分位、统一小数、保留单位 | 单位缺失/币种与 claim 不一致 → review |
| 版本 | 去 `v` 前缀、保留 prerelease | `0.25` vs `0.25.0` → review（语义不同） |
| 日期 | ISO/RFC 解析，时区转 UTC | 只有日期无时区且跨日 → review |
| 文本 | 大小写、空白、标点归一 | 语义改写不自动等同 |
| 许可证 | 标准化 SPDX（Apache-2.0/Apache 2.0） | 未知变体 → review |

**关键**：归一化后相同才允许 `no_change`；模糊归一化必须 review。

## 5. 独立性判定

- `independent_group` = 发布者/注册域 + 内容来源，不只是 URL host；
- 镜像、CDN、转载、同一组织的多个子域算**同一组**；
- 同一组多个来源不能凑“两源一致”；
- 示例：
  - `docs.tavily.com` 与 `github.com/tavily-ai/...` → 两个独立组（不同组织/仓库）；
  - `docs.tavily.com` 与 `cdn.docs.tavily.com` → 同一组；
  - `github.com/org/repo` 与 `github.com/org/repo/wiki` → 同一组。

## 6. Gate 规则（v0）

输入：current anchor、observations、claim temporal sensitivity、feature flag。

```text
R1 无 observation                         → reject
R2 归一化值 == anchor.value               → no_change
R3 归一化不确定（单位/币种/版本/日期歧义）  → review
R4 存在 ≥2 个独立 T1/T2 组，且归一化值一致
    且无 T1/T2 冲突                        → auto_update
R5 仅 1 个 T1/T2 组，无冲突                → review
R6 存在 T1/T2 冲突                         → review
R7 只有 T3/T4 支持                         → reject
R8 observation 比 anchor 更旧              → reject（不允许用旧证据覆盖新 anchor）
R9 anchor 不可达/无内容                    → reject
R10 同一 independent_group 的多个来源      → 只算 1 组（影响 R4/R5）
R11 自动更新需 feature flag = on，且候选
    accuracy_status = pending              → 先 candidate，再决定
```

**R4 的“无冲突”指：没有任何 T1/T2 observation 给出不同归一化值。**  
T3/T4 的不同值不阻断 auto，但必须记录在 candidate 里。

### 决策优先级

```text
R1 → R9 → R2 → R3 → R8 → R6 → R4 → R5 → R7
```

（先排除无证据/过期/无变化/歧义，再判冲突/一致性。）

## 7. 置信度（仅展示，不替代规则）

```text
authority = max(tier_weight)              # T1=1.0, T2=0.8, T3=0.5, T4=0.25
agreement = min(1.0, independent_groups / 2)
recency   = 1.0 if observation within claim window else 0.5
confidence = 0.4*authority + 0.4*agreement + 0.2*recency
```

- `auto_update` 仍必须满足 R4，不能仅凭 confidence；
- `review` 时展示 confidence 给评审。

## 8. 写回与回滚

Auto Update（仅 R4 + flag）：

1. 新建 `Anchor`，`supersedes=old.id`，记录 evidence hashes / gate version；
2. 旧 Anchor 标 `superseded`，**不删除**；
3. 记忆条目追加新版本，保留旧版本；
4. 写审计事件：old→new、evidence、gate decision、时间、操作者（auto）；
5. 支持 rollback：新 Anchor 标 `rolled_back`，旧 Anchor 恢复 active。

Review：

- Candidate 保留，`accuracy_status=pending`；
- 提供 `POST /admin/anchors/candidates/{id}/approve|reject`；
- 批准时才走写回；
- 拒绝记录理由。

## 9. 评估指标

| 指标 | 定义 | 目标 |
|---|---|---|
| Auto-update precision | 自动更新中正确的比例 | ≥0.95 |
| False update rate | 错误自动更新 / 全部自动更新 | ≤0.05 |
| Review coverage | 应更新但被送 review 的比例 | 可接受 ≤0.4 |
| Reject precision | 拒绝中确实不该更新的比例 | ≥0.9 |
| Gate agreement | Gate 决策与人工标注一致率 | ≥0.85 |
| Rollback rate | 自动更新后回滚比例 | ≤0.02 |

**False update rate 优先于覆盖率**：宁可多 review，不可多错写。

## 10. 标注集

- 文件：`benchmarks/accuracy_gate/labeled_cases.json`
- 30 条，覆盖：两源一致、单源、冲突、低权威、格式归一、单位歧义、旧证据、镜像、版本、日期时区；
- `expected.decision` 为 `auto_update / review / reject / no_change`；
- `synthetic_metadata=true`：事实来自公开资料，来源元数据为合成，用于规则测试，不是生产真值；
- 人工标注协议见 `docs/accuracy-labeling-protocol.md`。

## 11. 上线状态（2026-11-01）

已实现：

1. `AnchorCandidate` 表 + candidate 生命周期；
2. `POST /admin/anchors/{id}/candidates`（Gate 评估、候选持久化）；
3. `GET /admin/anchors/candidates`；
4. `POST /admin/anchors/candidates/{id}/approve|reject`；
5. `AUTO_UPDATE` 开关（`ACCURACY_AUTO_UPDATE`，默认 false）；
6. 自动更新仅对 R4 且开关开启生效；否则停留 pending；
7. 写回：新 Anchor + `supersedes` + 旧 Anchor `superseded`；无独立 memory 表，Anchor 即当前持久记忆；
8. **真实 revalidation → discovery → candidate 串联**：`revalidate_due` 对 content hash 变化的 anchor 提取 value hint，并通过 Tavily discovery 额外检索 2–3 个来源；多个 observation 一起进 Gate（单源 → review；多源独立一致 → auto 候选）；`AUTO_UPDATE` 默认关闭。

9. **Rollback 管理**：`POST /admin/anchors/{id}/rollback` + `/admin` 管理页（token 存 sessionStorage；列表、approve/reject/rollback）；
10. **Admin UI**：`/admin`（anchor 列表、candidate 列表、rollback 按钮）。

仍待完成：

- 60 条独立人工标注 + 对抗样本；
- rollback 管理端点（当前可通过新 Anchor 再 supersede 实现，未做 UI）；
- false update rate 在线监控；
- 评审 UI（当前 admin API 足够演示）。

## 12. v0 评估结果（2026-11-01）

- 规则实现：`src/yai_scout/detector/accuracy_gate.py`；
- 评估脚本：`scripts/eval_accuracy_gate.py`；
- 60 条标注（30 seed + 30 expansion）：**agreement 1.000**，auto_update precision 1.000（18/18）；
- 决策分布：auto 18 / review 22 / reject 10 / no_change 10。

**必须诚实说明**：这 60 条标签仍由规则作者设计，1.000 只证明“实现与设计一致”，不代表泛化。下一步需要 **独立人工标注/裁决** + 对抗样本，才可谈真实 precision。

## 13. 明确不做

- 不用 LLM 单独决定“新值正确”；
- 不把 freshness score 当 accuracy；
- 不自动覆盖旧 Anchor；
- 不允许单源自动更新；
- 不允许同一来源镜像凑数；
- 不在无标注集的情况下开启自动更新。




