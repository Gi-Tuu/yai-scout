# ADR-0001：双赛道选题 —— Bifrost-02 + Tavily-01（整合方案）

- 状态：**Proposed**（等待主办方书面确认双赛道/提交形态）
- 日期：2026-11-01
- 决策人：YAI Scout 项目组
- 相关：`docs/hackathon-rules-report.md`（调查全文与证据）

## 背景

官方于 2026-10-31 发布 6 道题（Bifrost 4 + Tavily 2）。官方渠道存在 4 处口径冲突：
1. 双赛道是否必选（平台公告"each track" vs 赛题图"either track"）；
2. 能否交两个项目（公告允许 vs Rules §8 只允许一个 vs 平台单次提交）；
3. 奖金（公告 $60K Tavily credits + $1K Bifrost cash vs 平台页 $65×100 + $11.5K）；
4. 截止日期（HackCulture/Luma 11/15 vs Tavily 社区页 11/22）。

## 决策

**做一个整合项目**：`YAI Scout — Freshness-aware Research Benchmark`，同时覆盖：
- **Bifrost-02**：Agent Benchmarking Platform（数据集 / Adapter 协议 / Runner / 排行榜 / 可复现报告）。
- **Tavily-01**：Stale-answer Detector（claim 抽取 → 时效分类 → Tavily 实时核验 → Freshness Score → 证据）。

**提交形态**：一个 GitHub 仓库、一次提交；README 用两节分别映射两轨评分点；`apps/benchmark` 与 `apps/detector` 两个入口。

## 理由

1. **对两种规则口径都安全**：若必须两轨，满足；若可选一轨，多做的部分不扣分。
2. **技术天然咬合**：freshness 是研究型 Agent 评测的一等指标；detector 就是 benchmark 的评分模块，不是两个产品硬拼。
3. **复用 G0 资产**：检索、来源台账、SSE、成本记账、YAI 适配层可直接复用；新增主要是 claim/verdict/runner/dashboard。
4. **单人 14 天可交付**：Must 集明确，且可裁剪（见报告 §F）。

## 后果

- 正面：单一故事线、单次提交、复用率高；同时命中两轨评委的关注点。
- 负面：范围比单题大；benchmark 数据集与 detector 准确率都要时间，需要严格执行 MVP 与冻结期。
- 缓解：11/12 功能冻结；若进度落后，优先保 detector（Tavily 轨）+ runner/榜单（Bifrost 轨），砍第三适配器、Bifrost 网关、历史趋势。

## 待确认（阻塞最终形态）

- 是否必须每轨各选一题？
- 两个独立项目能否在单次提交中提交？还是一个仓库整合？
- 整合项目能否同时获得两轨奖项？
- 奖金/credits 归属与有效期。

若回复"只能选一轨"：主投 **Tavily-01**（credits 价值更高），Bifrost-02 作为支撑模块写入 README，不单独领 Bifrost 奖。
若回复"必须两个独立项目"：同仓库拆两个入口 + 两份 README 章节，仍一次提交。
