# 规格：As-of Temporal Replay（D3）

> 版本 v2.0 · 2026-11-01 · 依赖：`scout_core/store` / `sources` / `evidence`
> 原则：**历史证据必须来自当时真实快照；没有就标 simulated，绝不伪造。**

## 1. 要解决的问题

同一个问题在不同时间点的答案可能不同。Replay 要回答：
- 当时的有效事实是什么？
- 现在的事实是什么？
- 哪些 claim 变了、哪些证据失效、哪些证据是新的？
- Agent 是否"发现"了变化（答案是否随之更新）？
- Freshness 分数如何变化？

## 2. 硬约束（先写清楚）

1. **Tavily 实时搜索不能还原历史互联网**；`as_of=2025-06` 参数不存在。
2. 历史证据只能来自：
   - Wayback Machine（Internet Archive）存档（首选）；
   - 我们手动保存的历史快照（附抓取时间、URL、hash）；
   - 官方页面自带的历史版本（如 GitHub Releases、Changelog）。
3. 没有历史快照的题，只能标 `mode=simulated`，UI 必须显示"模拟时间场景（非真实历史检索）"。
4. 历史 run 里，`effective_date > target_time` 的证据**一律不可用**（防未来泄漏）。
5. run 不可变：创建后不可修改关键字段；重跑生成新 run。

## 3. 快照获取与存储

### 3.1 获取

| 来源 | 方法 | 备注 |
|---|---|---|
| Wayback | `https://archive.org/wayback/available?url=<url>&timestamp=YYYYMMDD`；CDX：`http://web.archive.org/cdx/search/cdx?url=<url>&from=YYYY&to=YYYY&output=json` | 需要网络；优先同域官方页 |
| 手动存档 | 当前抓取 + `fetched_at` + `content_hash` | 作为"现在"的快照 |
| 官方历史 | GitHub Releases/Changelog、docs 版本页 | 天然带时间戳 |

### 3.2 存储

```text
snapshot_id, url, canonical_url, title, source_origin ∈ {wayback, manual, official_history},
content_hash, raw_path (data/snapshots/<hash>.html|txt), text_path,
published_at, updated_at, fetched_at, http_status, tier, notes
```

- 原文与抽取文本都存；`content_hash` 去重；
- 快照只读；删除需记录原因（演示期保留）。

## 4. 不可变运行记录（Immutable Run）

```text
run_id, app ∈ {benchmark, freshness}, task_id, agent_id,
as_of, mode ∈ {live, replay}, snapshot_ids[],
dataset_version, config_hash, code_commit,
started_at, finished_at, status,
result_hash (对结果 JSON 的 sha256)
```

- 创建后禁止 UPDATE 结果字段；需要修正 → 新 run + `supersedes` 字段；
- 报告展示 `snapshot_ids`，每条证据可点回快照。

## 5. 时间比较引擎（Temporal Comparison Engine）

输入：同一 `question`/`task_id` 的两个 run（as_of_1 < as_of_2）。
输出：

```json
{
  "task_id": "...",
  "as_of_1": "2025-06-01",
  "as_of_2": "2026-11-01",
  "claims": [
    {"claim_key": "tavily_free_credits", "claim_text": "...",
     "value_1": "500", "value_2": "1000", "change": "changed",
     "evidence_1": ["snap_.../url"], "evidence_2": ["..."],
     "freshness_1": 20, "freshness_2": 90}
  ],
  "new_claims": [...], "removed_claims": [...],
  "agent_answer_changed": true,
  "summary": {"changed": 1, "stable": 4, "new": 0, "removed": 0}
}
```

- `claim_key`：归一化（实体+谓词+单位），或人工标注的稳定 key；
- `change ∈ {stable, changed, new, removed, unverifiable}`；
- 只比较两次都有的证据集；缺失不推断。

## 6. Demo 设计（P1）

**题目候选**（必须先用 Wayback 验证存在快照）：

1. YAI Agent Core 版本：`v0.24.0`（2026-10-24 左右）→ `v0.25.0`（2026-10-31）——GitHub Releases/标签页有历史，最稳。
2. Tavily 定价：2025 年 archived docs 页 → 2026 现行页（若 Wayback 有快照）。
3. 同一事实的不同发布日期：不同来源给出不一致日期——这是"来源冲突"，不是时间漂移，用于 Conflicting 类。

**演示步骤（30–45 秒）**：
1. 同一问题，选择 as_of=2025-06 → 显示"当时的证据 + 答案 + Freshness"；
2. 切 as_of=2026-11 → 显示"当前证据 + 答案 + Freshness"；
3. 差异面板：哪条 claim 变了、旧证据失效、新证据出现、Agent 是否更新了答案；
4. 脚注：证据来自哪个快照、抓取时间；若为 simulated 必须标红。

**验收**：
- 每个 replay 结果可回答"证据来自哪个快照、何时抓取、为什么可用"；
- 无快照的题不得输出"已核验历史事实"；
- 对比表可导出。

## 7. 实现顺序

| 步骤 | 内容 | 优先级 |
|---|---|---|
| 1 | snapshot 表 + 手动/当前快照 | P0（当前证据） |
| 2 | Wayback 抓取脚本 + 快照校验 | P1 |
| 3 | 不可变 run + result_hash | P1 |
| 4 | 对比引擎 + 漂移报告 API/UI | P1 |
| 5 | 时间旅行可视化（P2） | P2 |

## 7.5 替代来源：GitHub Releases（official_history）

archive.org 不可达时，用**官方 release 历史**作为真实历史证据：

- 脚本：`scripts/capture_github_history.py --repo Gi-Tuu/yai-agent-core`
- 每条 release 一个快照，`published_at` = 官方发布时间；`origin=official_history`
- replay 只使用 `published_at <= target_time` 的快照，且要求快照与 claim 主题相关（URL/关键词）

**实测（2026-11-01）**：

| as_of | 可用最新 release | 判定 |
|---|---|---|
| 2026-10-28 | v0.24.0（2026-10-27） | **STALE 24**（claim 0.25.0 与当时最新版本矛盾） |
| 2026-11-01 | v0.25.0（2026-10-31） | **FRESH 88**（官方 release 支持） |

这是**真实历史证据**（GitHub 官方 API 时间戳），不是伪造的 Wayback 页面；它只覆盖"版本/发布"类事实，不覆盖网页内容快照。

## 8. 风险

- **Wayback 不可达（实测 2026-11-01）**：当前环境访问 archive.org 失败（超时/代理），无法自动抓取历史快照 → 演示默认 `simulated`，或换网络环境后用 `scripts/capture_snapshot.py` 补抓；**不得伪造历史证据**。
- Wayback 无快照 / 被墙 → 换题或标 simulated；
- 页面结构变化导致抽取失败 → 保存原文，抽取失败标 `unparsed`；
- 时区/发布日期歧义 → 统一 UTC，记录原始字符串；
- 演示数据过时 → 赛前 11/12 重新校验快照可用性。

