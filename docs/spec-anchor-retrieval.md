# Anchor-First Freshness Retrieval（设计稿，未实现）

> 日期：2026-11-01 · 状态：设计稿，本轮不写代码。  
> 目标：把“记忆里已知”和“记忆里没有”的新鲜度检查分开，减少重复检索过期信息，并为记忆更新提供可审计的锚点。

## 1. 问题

当前 Freshness 检测器对每条 claim 都走“检索 → 取证据 → 判定”。这在 demo 可行，但对长期运行的 Agent 有两个浪费：

1. **已知事实被反复宽泛检索**：每次都可能重新拉到旧页面/旧快照，增加噪声与成本。
2. **记忆与证据脱节**：Agent 记忆里说“Tavily 免费 1,000”，但没有记录“这个值来自哪个来源、何时核验过”，无法增量更新。

## 2. 两个入口

### A. Memory-known（记忆里已有）

- 记忆条目携带 **Anchor**：`canonical_url`、`source_tier`、`last_verified_at`、`last_value`、`valid_from`、`supersedes`。
- 流程：
  1. 取出 Anchor；
  2. **从最新信息向锚点检索**：先取该来源的当前页面/最新 release，再与锚点记录的值对比；
  3. 只有 Anchor 不可达/模糊时，才退回宽泛搜索；
  4. 若值变化：写新 Anchor（`supersedes` 旧值）、更新记忆、记录事件；不删除旧记录。
- 目的：不再把“旧页面”当当前证据；减少无效检索。

### B. Memory-unknown（记忆里没有）

- 没有 Anchor，必须检索。
- 流程：**从新往旧**（latest → older）：先限定最近时间窗/最新页面，逐步放宽；找到第一个权威来源后建立 Anchor；若权威来源相互冲突，标 `CONFLICTED` 并保留双方。
- 目的：避免默认检索到过时页面；先建立锚点，下次走 A。

## 3. 锚点模型（提案）

```text
Anchor:
  id
  canonical_url
  source_tier            # 1..4
  entity                 # 例如 "Tavily free plan credits"
  relation               # 例如 "monthly_credits"
  last_value             # 例如 "1000"
  last_verified_at
  valid_from
  valid_until?           # 可选
  supersedes             # 旧 Anchor id
  snapshot_id            # 对应证据快照
  status                 # active / superseded / unreachable
```

- 一个记忆条目 → 一个或多个 Anchor（按 claim 粒度）。
- 旧 Anchor 不删除，只标 `superseded`，用于 replay/审计。
- 所有更新写事件：`anchor_updated`、`memory_updated`、`evidence_snapshot`。

## 4. 与 Freshness 的关系

- Freshness 回答“**在目标时间点，这个值是否仍然成立**”；
- Anchor 回答“**这个值应该去哪里核验、上次核验是什么时候/什么值**”；
- Anchor 让 Freshness 从“每次全量搜索”变成“定向核验 + 必要时搜索”。

## 5. 与 Accuracy 的关系（明确分开）

**Freshness ≠ Accuracy**：

- Freshness：值是否与目标时间点的权威来源一致、是否过期。
- Accuracy：值是否真实/正确（需要独立 ground truth、交叉验证、领域校验）。

Anchor 只解决“去哪核验、何时核验、旧值是什么”；它不能证明来源本身正确。  
Accuracy 需要单独一层（例如多源一致性、领域规则、人工标注、对抗校验），**不应混入 freshness score**，否则会出现“来源新但内容错 → 高分”的误判。本轮只记录这个边界，下一轮再设计 Accuracy Layer。

## 6. 检索策略细节

| 情况 | 查询构造 | 证据选择 | 更新 |
|---|---|---|---|
| 已知 + Anchor 可达 | `site:<anchor.domain> <entity> <relation> latest`；或来源 API（GitHub releases、pricing page） | 当前页面/最新 release；与 `last_value` 对比 | 变化→新 Anchor + 记忆 |
| 已知 + Anchor 不可达 | 宽泛检索，时间从新到旧；优先同域/官方 | 找到替代官方来源后重建 Anchor | 新 Anchor，旧标 unreachable |
| 未知 | `entity relation latest 2026`；时间过滤新→旧 | 第一个权威来源；冲突则双源 | 初始 Anchor |
| 冲突 | 分别核验双方时间与权威性 | 保留双方，`CONFLICTED` | 不强行合并 |

## 7. 最小实现计划（P1，未做）

1. `Anchor` 表 + `AnchorStore`（SQLite，复用现有 store 模式）；
2. 检测器增加 `anchor` 可选输入：有 anchor 时只定向核验；
3. `replay` 使用 snapshot 时间，不访问网络；
4. 更新事件与 `supersedes`；
5. 测试：anchor 命中、值变化、anchor 失效、冲突、replay；
6. 与现有 freshness 输出兼容：新增 `anchor_id` / `anchor_updated` 字段，不改变状态机与分数公式。

## 8. 风险

- Anchor 漂移（URL 变更/站点改版）→ 保留 canonical + 多候选；
- 官方页面删除 → 标 unreachable，回退搜索；
- Anchor 指向错误来源 → 需要 source tier/官方域名白名单 + 人工复核；
- 记忆更新与证据更新不同步 → 事件化、可重放；
- 不要把 Anchor 当成 Accuracy 证明。

## 9. 验收（未来）

- 同一 claim 第二次检查不再宽泛搜索（可用请求数/延迟度量）；
- 值变化后 1 次核验即更新记忆与 Anchor；
- 旧 Anchor 可 replay，且不被覆盖；
- freshness 分数公式不变。
