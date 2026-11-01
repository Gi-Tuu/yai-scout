# Anchor-First Freshness Retrieval（修正版设计）

> 日期：2026-11-01 · 状态：**MVP 部分实现**（replay-only anchor evidence）；自动记忆更新与 Accuracy gate 未实现。  
> 目标：区分“记忆里已知”和“记忆里没有”，用锚点降低重复检索，同时避免把锚点当成真理。

## 0. 先修正一个危险直觉

原思路：“有来源锚点 → 聚焦锚点核验 → 减少重新检索”。  
这个方向有价值，但有一个**确认偏误**：

> 如果锚点是 2024 年的官方页，页面今天仍写着 500，锚点核验会得到“500 仍在”，从而误判 FRESH；而当前值可能已在另一个页面变成 1,000。

因此本设计明确：

- **Anchor 是“上次核验的凭证/来源指针”，不是“当前值的证明”。**
- **Anchor-only verification 不能保证 freshness。**
- 对 SENSITIVE / VOLATILE claim，锚点只用于**定向核验 + 降低搜索成本**，仍需 discovery。
- 对 STABLE / SLOW claim，才允许较长 TTL 的锚点复验。
- **更新记忆前必须有 Accuracy gate**；“来源变了” ≠ “新值是对的”。

## 1. 两个入口

### A. Memory-known（记忆里已有）

- 记忆条目携带 **Anchor**：来源 URL、来源等级、上次值、上次核验时间、内容 hash、有效期。
- 流程（修正后）：

```text
claim
  → 解析 entity/relation，找 Anchor（可多个）
  → 按 temporal sensitivity 选择策略：
      STABLE/SLOW       : 锚点复验（TTL）
      SENSITIVE/VOLATILE: 锚点复验 + 定向 discovery（同域 changelog/pricing/官方页）
  → 与锚点值做 diff（值 + content hash）
  → 变化 → 生成 candidate update（不直接写记忆）
  → Accuracy gate（多源/权威/人工）通过 → 新 Anchor + 记忆更新
  → 旧 Anchor 保留 superseded，可 replay
```

- **不是“走向锚点”，而是“以锚点为对比基准，从当前信息找差异”。**

### B. Memory-unknown（记忆里没有）

- 无 Anchor，执行 discovery：

```text
authority-first（官方域名/一手来源）
  + recency filter（新→旧）
  → 找到首个权威来源 → 建立 Anchor
  → 若多个权威来源冲突 → CONFLICTED，保留双方
```

- 不能只按“最新”排序：最新页面可能是 SEO/转载/错误营销页；权威性优先，时间次之。

## 2. Anchor 模型

```text
Anchor:
  id
  claim_key              # 归一化 claim（数字替换为 #），用于匹配
  claim_text             # 人类可读
  url
  source_tier            # 1..4
  last_value
  content_hash           # 页面内容 hash，检测“同 URL 内容变化”
  published_at
  updated_at
  last_verified_at
  valid_from / valid_until?
  supersedes             # 旧 Anchor id
  status                 # active | superseded | unreachable | disputed
```

补充：

- 一个 claim 可对应**多个 anchor**（官方页、changelog、文档），不是单一 URL。
- Anchor 可追踪内容 hash，避免“值没变但页面已改”被忽略。
- 旧 anchor 不删除，用于 replay/审计。

## 3. 与 Freshness / Accuracy 的关系

| 层 | 回答 | 数据 |
|---|---|---|
| **Freshness** | 目标时间点，这个值是否仍与权威来源一致？ | 证据时间、有效期、来源等级、diff |
| **Accuracy** | 这个值本身是否真实/正确？ | 独立 ground truth、多源一致性、领域规则、人工标注 |
| **Trust** | 两者并列展示，不合成黑箱分 | — |

**绝不能用 freshness 分数替代 accuracy**：来源新但内容错，freshness 可能高，accuracy 必须低。

## 4. 检索策略

| 情况 | 查询/证据 | 是否跳过 discovery |
|---|---|---|
| STABLE + anchor 可达 | 定向抓取 anchor 当前页；TTL 内只做轻量复验 | 可（TTL 内） |
| SLOW + anchor 可达 | 定向抓取 + 周期性 discovery | 低频 discovery |
| SENSITIVE + anchor 可达 | 定向抓取 + 同域 discovery + 必要时宽泛搜索 | **否** |
| VOLATILE | 每次实时核验 + 多源 | **否** |
| anchor 不可达/内容 hash 变化 | 触发 discovery，寻找替代权威源 | 否 |
| unknown | authority-first + recency | — |

## 5. 更新与安全

- 更新流程：`observation` → `candidate` → `accuracy gate` → `active anchor + memory update`；
- 不允许静默覆盖；旧值只标 superseded；
- 更新事件写入审计日志（时间、来源、diff、gate 结果）；
- **SSRF 防护**：Anchor URL 不允许任意由公开 API 指定后立即抓取；MVP 只允许从已存 snapshot 读取（replay），live 抓取需受控 allowlist。

## 6. MVP 实现范围（本次）

**已实现**：

1. `Anchor` 数据模型 + SQLite `anchor` 表（append-only，不删旧记录）；
2. `POST /freshness/anchors` / `GET /freshness/anchors`（仅存元数据，不抓取 URL）；
3. `POST /freshness/verify` 增加 `use_anchors`；replay 模式下按 `claim_key` 匹配 anchor，并从**已存 snapshot**注入锚点证据；
4. Verdict 增加 `anchor_id` / `anchor_status`（used/unreachable），**不改变状态机与分数公式**；
5. live 模式暂不抓取 anchor URL（避免 SSRF），标记 `unreachable` 或忽略；
6. 测试：anchor 存储、replay 锚点证据注入、不改变原有评分。

**未实现（下一阶段）**：

- live 锚点定向抓取 + allowlist；
- 多 anchor 选择/权威度排序；
- content hash diff；
- accuracy gate 与自动记忆更新；
- TTL 调度与后台复验。

## 7. 验收（未来）

- SENSITIVE claim 在 anchor 可达时，检索次数/延迟下降，但 discovery 仍执行；
- anchor 失效时自动回退，不误判 FRESH；
- 值变化后生成 candidate，不直接覆盖记忆；
- 旧 anchor 可 replay；
- freshness 分数公式不变。

## 8. 风险

| 风险 | 缓解 |
|---|---|
| 锚点确认偏误 | SENSITIVE/VOLATILE 强制 discovery；锚点只作基准 |
| 单锚点错误/漂移 | 多 anchor、source tier、content hash、unreachable |
| 把 anchor 当 accuracy | 分离分数；写记忆前 accuracy gate |
| SSRF | 公开 API 不抓取任意 anchor URL；MVP replay-only |
| 记忆污染 | append-only + candidate + gate；不静默覆盖 |
| 成本/延迟 | TTL 按 sensitivity；缓存 snapshot |
