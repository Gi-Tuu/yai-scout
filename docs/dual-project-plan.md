# 双项目执行计划：MVP、排期、风险与整合展示

> 版本 v1.0 · 2026-11-01 · 适用：Project A（Benchmark）+ Project B（Freshness）
> **v2 变更**：差异化升级为 Freshness-aware Benchmarking；P0/P1/P2 与模块验收以 [`differentiation-spec.md`](differentiation-spec.md) 为准（本文 §2 的 MVP 清单相应扩展：Freshness 指标、claim-level 评测、Pareto、Adapter 协议）。
> 目标截止：**2026-11-15 23:59 IST = 北京 11-16 02:29**；计划 11-15 12:00 前提交。

## 1. 共享底座先行（避免瓶颈）

| 顺序 | 交付 | 完成标准 |
|---|---|---|
| S1（11/01–11/02） | `scout_core/contracts` 冻结：`AgentAdapter` / `SourceProvider` / `EvidenceExtractor` / `Scorer` + Pydantic 模型 | 两个 app 都只依赖 contracts，可独立启动 |
| S2（11/02–11/03） | `store` / `sources` / `trace` / `eval` 迁移完成 | 现有 detector/benchmark 代码跑在 core 上，测试绿 |
| S3（11/03 之后） | 共享层**只修 bug**，不再加新能力 | 任何 core 变更必须两套测试同时通过 |

> 规则：**共享层不是第三个产品**。只实现两个 app 都真正需要的能力；单边需求放 app 内。

## 2. MVP 验收（合并清单）

### Project A — Benchmark（Bifrost-02）

- [ ] 3 类 Adapter（HTTP / CLI / Python）各 ≥1 个 Agent，其中 ≥1 个非 YAI、≥1 个外部进程
- [ ] 15 题数据集（10 公开 + 5 隐藏），金标值 + 来源
- [ ] 一次 run：15 题 × 3 Agent，失败不中断，结果落库
- [ ] 6 项指标（准确率/完成率/证据质量/token/时延/失败率）+ 榜单 + 单题下钻
- [ ] `config_hash` 相同 → 分数一致（±0.02）
- [ ] 报告导出（Markdown/JSON）

### Project B — Freshness（Tavily-01）

- [ ] 5 组对抗答案（旧价格/旧版本/旧法规/旧 CEO/正确对照）可检测
- [ ] 20 条标注 claim 上：抽取覆盖 ≥80%，stale precision ≥0.8 / recall ≥0.7（规则版基线）
- [ ] 每条 verdict 有证据或明确 `unverifiable`；证据带 URL + 时间
- [ ] 报告含修正建议；6 条 claim ≤60s、≤12 credits
- [ ] 无模型 key 时规则版可完整跑通

### 共享验收

- [ ] 两个 app 可**独立启动**（`SCOUT_MODE=benchmark` / `freshness`），互不依赖
- [ ] 两个 app 各自有 README、Demo 入口、验收记录
- [ ] 全部测试绿；`ruff` + `mypy` 绿；依赖锁定（uv.lock）
- [ ] 许可证/NOTICE 完整（YAI MIT、Tavily 条款、字体许可）

## 3. 14 天排期（北京时间）

| 日期 | 共享层 | Project A | Project B | 门禁 |
|---|---|---|---|---|
| 11/01（日） | 决策冻结；接口草案；仓库结构 | 数据集初稿（15 题） | LLM 抽取接口设计 | 主办方追问邮件发出 |
| 11/02（一） | **contracts 冻结**；store/sources 迁移 | app 骨架可启动 | app 骨架可启动 | **G1**：两个 app 独立启动 |
| 11/03（二） | trace / eval 迁移；契约测试 | 3 类 Adapter + Runner | LLM 抽取接入（key 到位后） | — |
| 11/04（三） | 成本台账 / 缓存 | 评分引擎 + 榜单 API | Tavily 验证 + 证据表 | — |
| 11/05（四） | — | Benchmark Dashboard | Freshness 评分 + 报告 | — |
| 11/06（五） | 共享层 bugfix | 单题下钻 + 轨迹 | 报告 UI + 修正建议 | **G2**：两 MVP 主流程跑通 |
| 11/07（六） | — | 失败重试 / 超时 / 预算 | 冲突检测 / 多来源 | — |
| 11/08（日） | — | 15 题 × 3 Agent 全跑 | 20 条标注集评测 | — |
| 11/09（一） | — | 可复现校验 + 导出 | As-of 时间旅行（Should） | **G3**：评测数字达标 |
| 11/10（二） | — | 外部 Agent 接入演示 | 对抗样本 + 误判分析 | — |
| 11/11（三） | — | README-A / PPT-A / 视频 A | README-B / PPT-B / 视频 B | 部署两个入口 |
| 11/12（四） | 冻结 | 修 P0 / 录屏 | 修 P0 / 录屏 | **G4**：功能冻结 |
| 11/13（五） | — | 提交材料 A | 提交材料 B | 视频定稿 |
| 11/14（六） | — | 彩排 + 最终部署 | 彩排 + 最终部署 | **G5**：可提交 |
| 11/15（日）12:00 | — | **提交（一仓库两入口 + 合并视频）** | 同上 | 离截止 14.5h |

**容量核算**：共享 14h + Benchmark 30h + Freshness 28h + 集成/文档/视频 16h + 测试缓冲 12h ≈ **100h**；按 7.5h/天 × 15 天 ≈ 112h，余量 12h。若每天 <7h：砍 Should（Bifrost 网关、as-of、批量 API、历史趋势），保 Must。

## 4. 砍功能顺序（从轻到重）

1. Benchmark：Bifrost 网关模式 → 历史趋势 → 报告 PDF
2. Freshness：批量 API → as-of 时间旅行 → 证据快照
3. 共享：非必要指标 → 高级统计
4. **绝不砍**：3 类 Adapter、15 题、6 指标、claim 级证据、Freshness Score、逐条来源

## 5. 整合展示（任务 6 的结论）

**做，但不是唯一入口**：

| 层 | 内容 | 独立性 |
|---|---|---|
| 统一 Landing `/` | 两个卡片：Benchmark / Freshness；一句总介绍 + 两个赛道映射 | 仅导航 |
| Project A 入口 `/benchmark` | 独立 Dashboard + 独立 README + 独立视频 | **必须可独立访问** |
| Project B 入口 `/freshness` | 独立 Dashboard + 独立 README + 独立视频 | **必须可独立访问** |
| 部署 | 同一容器双路由（`SCOUT_MODE=all`），也可拆两个容器 | 两种都支持 |

**不做**：为了"统一感"把两个产品合成一个页面流；不在 Landing 上堆功能。

## 6. 提交材料矩阵（平台单次提交时）

| 材料 | Project A | Project B | 合并提交时 |
|---|---|---|---|
| GitHub | monorepo 链接 + `apps/benchmark` | monorepo 链接 + `apps/freshness` | 一个链接 + 两个子目录说明 |
| README | `apps/benchmark/README.md` | `apps/freshness/README.md` | 根 README 导航 |
| Demo 视频 | 2 分钟（A 脚本） | 2 分钟（B 脚本） | **4 分钟合并版**：前 2 分钟 A、后 2 分钟 B，章节字幕 |
| PPT | 5 页 A | 5 页 B | 10 页合并（两章） |
| 在线 Demo | `/benchmark` | `/freshness` | 同一域名两个路径 |
| AI 使用说明 | 各自一节 | 各自一节 | 合并文档两节 |

> 若主办方开放两次提交：直接分别提交 A / B，材料无需合并。

## 7. 风险清单

| # | 风险 | 概率 | 影响 | 触发信号 | 缓解 |
|---|---|---|---|---|---|
| R1 | 平台只允许一次提交，双作品如何放未确认 | 高 | 中 | 主办方未回复 | 默认"一仓库两入口 + 合并视频"；材料里写清两轨映射 |
| R2 | 双项目工作量超容量 | 高 | 高 | G2 延期 >12h | 砍 Should；共享层冻结；周末 9–10h |
| R3 | DeepSeek key 未到，LLM 抽取无法验证 | 中 | 中 | 11/03 仍无 key | 规则版先跑通；LLM 后接（接口已留） |
| R4 | Tavily 额度/限流 | 中 | 中 | 429 / 余额告警 | 缓存、claim 上限、学生计划、$12 充值 |
| R5 | Benchmark 被质疑"只测 YAI" | 中 | 高 | 评审提问 | 3 类 Adapter + 外部 Agent 现场接入 + 明确 synthetic 标注 |
| R6 | Freshness 误判（假阳性） | 中 | 高 | 标注集 precision <0.8 | 收紧 stale 阈值；权威来源优先；展示冲突 |
| R7 | 共享层变更拖垮两边 | 中 | 中 | 契约测试红 | 11/02 后冻结接口；变更双测 |
| R8 | Demo 现场翻车 | 中 | 高 | 部署/网络失败 | 录屏为主 + 本地 fixtures + 预跑 |
| R9 | 许可证叙述错误（AGPL vs MIT） | 低 | 中 | 材料引用错 | 以事实 MIT 为准；提交材料写 MIT + 声明 |
| R10 | 范围蔓延（想加功能） | 高 | 中 | 每日计划外新增 | 变更需 ADR + 等量削减 |
| R11 | 单人疲劳 | 中 | 中 | 连续 3 天 <5h 睡眠 | 22:00 收工；周末留半天 |

## 8. 每日节奏

- 09:00–12:00 最高价值模块（共享层/核心算法）
- 14:00–18:00 UI/测试/文档（可并行 AI 代理）
- 20:00–22:00 联调 + 更新 README/ADR；**22:00 后不写新功能**
- 每天 `git tag daily-YYYYMMDD`；每完成一个 Must 更新验收清单。
