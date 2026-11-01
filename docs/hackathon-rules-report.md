# Geek Room Global AI Hackathon — 官方赛题调查与立项建议

> 调查时间：2026-11-01 10:30–11:10（UTC+8）｜调查人：YAI Scout 项目组
> 方法：官方平台 API 原始 JSON（已存档）+ 官方赛事页 + 官方公告 + 合作方官方文档；LinkedIn/Instagram 因地区/登录限制未能直读，相关处标注来源等级。
> 约定：**[官方原文]** = 官方页面/API/公告逐字；**[官方图片]** = 官方赛题图（由核查员读取，未能直读原图）；**[推断]** = 我们的判断；**[待确认]** = 官方无明文。

---

## 0. 结论摘要（先看这 8 条）

1. **赛事仍在报名与提交期**：官方平台显示 `is_registration_open=true`，提交窗口 **2026-11-01 00:00 IST → 11-15 23:59 IST**（北京 11/1 02:30 → **11/16 02:29**），评审 **11/29 19:00–23:59 IST**（北京 21:30 → 次日 02:29）。共 1,407 人报名。**[官方 API]**
2. **6 道题已正式发布**（10/31 17:13Z 公告）：Bifrost 4 题 + Tavily 2 题；你提供的 6 条标题与官方逐字一致。**[官方公告 + 官方图片]**
3. **双赛道规则存在官方口径冲突**：平台公告写 "Every team must select one problem statement from **each track**. You can either build two separate projects or combine both challenges into one integrated solution."；而 Rules §8 写 "Each team may submit **only one final project**"，官方赛题图又被读出 "Pick 1 from either track, or combine one from each"。→ **必须向主办方确认**（见 §G 邮件）。
4. **安全策略不依赖冲突结论**：无论"必须两轨"还是"可选一轨"、无论"一项目还是两项目"，**做一个同时覆盖 Bifrost-02 + Tavily-01 的整合项目、放进一个仓库、一次提交**都能同时满足两种口径——这是本报告的默认方案。
5. **奖金口径必须修正**：Tavily 的 $30K/$20K/$10K 是 **credits（以美元计价）**，不是现金；Bifrost 只有 **$1,000 现金**（$500/$300/$200）+ 直通面试。平台奖项页仍写 "Tavily $65 credits ×100"，**已过期**，不要引用。**[官方公告 + 官方图片]**
6. **提交机制**：平台只有一个提交表单，必填 **GitHub 链接**，选填 Demo 视频与 PPT；`allow_multiple_submissions=false`；同时 Rule 8 写 "Each team may submit only one final project"。→ 两个独立项目怎么交，**待确认**。**[官方 API]**
7. **每人/每队必须先在平台上建队**（哪怕是单人）：官方 10/20 公告原文 "Even if you're participating solo, you still need to create a team to be eligible"。**[官方公告]**
8. **最优选题**：**Bifrost-02（Agent Benchmarking Platform）+ Tavily-01（Stale-answer Detector）做成一个整合项目** —— "Freshness-aware Research Benchmark"。理由与替代方案见 §D。
9. **日期还有一个官方口径差**：HackCulture/Luma（Tavily 联合主办）写 **11/1–11/15**；Tavily 社区页把同一链接标成 **"Nov 1–22"**。→ 按 **11/15** 执行（更早、更安全），并在邮件里顺带确认。

---

## A. 赛事状态

| 项目 | 状态 | 证据 |
|---|---|---|
| 是否仍可报名 | **是** | API `is_registration_open: true`；报名截止 2026-11-15 23:59 IST |
| 报名截止 | 2026-11-15 23:59 IST（北京 11-16 02:29） | `phases[registration].end_datetime=2026-11-15T18:29:00Z` |
| 题目公布 | 已于 2026-10-31 发布（公告时间 17:13Z） | 公告 "[IMP] Global AI Hackathon: Problem Statements & Prizes Announced!" |
| 提交窗口 | 2026-11-01 00:00 IST → 11-15 23:59 IST | `phases[submission]`：`2026-10-31T18:30:00Z` → `2026-11-15T18:29:00Z` |
| 评审 | 2026-11-29 19:00–23:59 IST（北京 21:30–次日 02:29） | `phases[judging]`：`2026-11-29T13:30Z`–`18:29Z` |
| 赛事总周期 | 2026-10-09 → 11-29 | API `start_datetime` / `end_datetime` |
| 报名规模 | 1,407 人、40+ 国家 | API `total_participants: 1407`；公告 |
| 最新规则变更 | ① 题目与奖金 10/31 发布；② 官方公告新增"双赛道选题"说明；③ 平台 Themes 区**未同步**（仍 REVEALING SOON） | 平台公告；页面抓取 |
| 官方更新渠道 | **WhatsApp 群**（10/26 起公告明确"所有重要更新在 WhatsApp 群"）+ Discord | 公告原文；`https://chat.whatsapp.com/GkRxNNSAhBP0y89HG8SGpa` |
| 联合主办（Tavily） | **Luma 活动页由 Geek Room 与 Tavily Events 联合主办**：Oct 31 2:30 PM EDT → **Nov 15 1:00 PM EST** | https://luma.com/33nivwqh |
| 第二日期口径 | Tavily 社区页把同一 HackCulture 链接标成 **"Global AI Hackathon, Nov 1–22, 2026"** | https://www.tavily.com/community |
| 建队要求 | **单人参赛也必须建队**；未建队不具资格 | 官方公告（2026-10-20）"Even if you're participating solo, you still need to create a team to be eligible" |

### A.2 官方口径冲突清单（4 处，全部需要确认）

| # | 冲突点 | 来源 A | 来源 B | 影响 | 本报告采纳 |
|---|---|---|---|---|---|
| C1 | 双赛道是否必选 | 平台公告（10/31）：**每轨各选一题** | 官方赛题图：**Pick 1 from either track** | 决定要不要做两题 | 按"两轨都做"执行（对两种口径都安全） |
| C2 | 能否交两个项目 | 平台公告：**可 build two separate projects** | Rules §8：**only one final project**；平台 `allow_multiple_submissions=false` | 决定提交形态 | 一个整合项目 + 一个仓库 + 一次提交 |
| C3 | 奖金总额 | 公告：Bifrost $1,000 现金 + Tavily $60,000 credits（top 3）+ $8,000 参与者 credits | 平台奖项页：$1,000 现金 + Tavily $65 credits ×100 + Omnidimension $50 ×100；总奖池 $11.5K | 材料引用风险 | 以公告 + 官方图片为准，平台旧数据不引用 |
| C4 | 截止日期 | HackCulture / Luma：**11/15** | Tavily 社区页：**11/22** | 倒排计划 | 按 **11/15** 执行（更早、更安全） |

> 注意：HackCulture 的 Themes 区、Prizes 区**滞后于公告**。以 10/31 公告 + 官方赛题图为准，平台旧数字不要写进提交材料。

---

## B. 双赛道参赛规则（逐项回答）

### B.0 官方原文（最关键的两段）

**平台公告（2026-10-31 17:13Z，逐字）**：
> "Every team must select one problem statement from each track. You can either build two separate projects or combine both challenges into one integrated solution."

**官方赛题图（核查员读取，未能直读原图）**：
> "Pick 1 from either track, or combine one from each" / "Bifrost statements get priority"

→ **这两句在"是否可以只做一个赛道"上不一致**：公告说每轨各选一题（=两轨都要），图说可从任一轨选一题。本报告按"**两轨都做**"给默认方案（对两种口径都安全），并把此冲突列为必须发邮件确认的第一问。

### B.1 五问结论表

| 参赛形式 | 是否允许 | 官方证据 | 置信度 |
|---|---|---|---|
| 一人同时参加两个赛道 | **允许（且公告要求每轨各选一题）** | 平台公告 "one problem statement from each track"；个人可参赛（Eligibility） | 高（但受 B.0 冲突影响） |
| 同一队伍同时参加两个赛道 | **允许** | 同上；团队 1–4 人 | 高 |
| 同一队伍提交两个独立项目 | **存在官方冲突**：公告允许，Rules §8 禁止 | 公告 "build two separate projects" **vs** Rules §8 "only one final project" + 平台单次提交 | 低（需书面确认） |
| 一个项目同时参加两个赛道 | **允许** | 公告 "combine both challenges into one integrated solution" | 高 |
| 分别获得两个赛道的奖项 | **官方尚未确认** | 公告暗示整合方案可同时满足两轨，但无"可同时获奖"明文；无禁止条款 | 低 |
| 一人/一队最多提交几个 | **平台仅允许 1 次提交**（`allow_multiple_submissions=false`）；Rule 8 写 1 个最终项目 | API phase 配置 + Rule 8 | 高 |
| 是否必须先选 Track | 提交表单**没有** Track 字段（只有 GitHub / Demo / PPT） | API `submission_questions` | 高 |
| 截止前能否改赛道 | 官方尚未确认（提交通常可覆盖？平台未给说明） | — | 待确认 |
| 两赛道是否分别创建 Submission | 平台只支持 1 次提交 → 推测**不会**分别创建；需确认 | API | 中 |
| 同一项目重复投两个赛道 | 与"整合项目"是同一件事；官方允许整合方案 | 公告 | 高 |

### B.2 冲突的合理解读（我们的判断，非官方）

- "两个独立项目"和"一队一次提交 / Rule 8"**存在文本冲突**：公告（10/31，更新）明确允许两项目，Rules §8（更早的通用模板）说只允许一个最终项目，平台又只给一次提交。最可能的情况是**主办方希望一个提交里覆盖两题**（整合或同仓库双项目），但**不能替主办方裁决**，必须书面确认。
- "每轨各选一题"与"可选一轨"的矛盾，最可能源于**公告是最终口径、赛题图是发布文案**；同样需要书面确认。
- **默认执行方案**：一个整合项目 + 一个仓库 + 一份提交，同时明确映射两轨评分点（见 §D/F）。若主办方回复"只能选一轨"，则把整合项目主投 Tavily-01，Bifrost-02 作为支撑模块在 README 中说明（不单独领 Bifrost 奖）；若回复"必须两个项目"，则同仓库拆 `apps/benchmark` 与 `apps/detector` 两个入口，仍一次提交。

### B.3 提交表单实际字段（官方 API 原文）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| Github link of the Project | URL | **是** | 唯一必填项 |
| Demo Video Link | URL | 否 | 建议一定给（评审 5 小时窗口） |
| PPT File | 文件 | 否 | 建议给（项目说明/AI 使用说明可放这里） |

> 结论：**项目描述、AI 使用说明没有独立字段**，必须写进 README / PPT / 视频。提交材料清单按 Charter §10.4 执行。

---

## C. 赛题技术分析（6 题）

评分口径（通用）：总体 6 维 Innovation / Technical execution / Problem & impact / Use of AI / UX / Scalability；**两轨均未公布专属 rubric**。下表"匹配度"指与 YAI Scout 现有资产（检索、证据台账、验证、报告、G0 代码）的复用程度。

> 获奖名额：**Tavily 明确 "top 3 teams"**（平台公告原文）；**Bifrost 3 名获奖者**来自官方赛题图（平台公告未写数量）。Bifrost 官方图另称 "Bifrost statements get priority"——平台公告未提，若属实，整合方案应把 Bifrost-02 的完成度放在第一位。

| 赛道/题 | 类型 | 难度 | 14 天成本 | 与 Scout 匹配 | 主要风险 | 建议 |
|---|---|---|---|---|---|---|
| **Bifrost-01** 最少 token 的 coding agent | 工程型 Agent + 基准 | 高 | 高（8–10 人日） | 低（Scout 不是 coding agent；YAI 有工具循环但无 coding 基准） | 对手强、正确率难保证、token 计量口径易被抓 | 不做 |
| **Bifrost-02** Agent 评测平台（非模型评测） | 平台/基础设施 | 中高 | 中（5–6 人日） | **高**（YAI eval harness 思路 + Scout 的证据质量指标 + G0 的 runner 骨架） | "又一个排行榜"缺乏新意；数据集与适配器工作量被低估 | **首选** |
| **Bifrost-03** 自主渗透测试 Agent | 安全 Agent | 高 | 高（7–9 人日） | 低 | 法律/伦理风险、必须沙箱、授权目标难获取 | 不做 |
| **Bifrost-04** 给开源网关加缺失功能 | 开源贡献 | 中 | 中（4–6 人日） | 低（Go/TS 技术栈；与 Tavily 题无协同） | 需熟悉 Bifrost 代码；功能价值难被评委感知 | 不优先 |
| **Tavily-01** 过时答案检测器 | 核验 Agent | 中 | 中（5–6 人日） | **最高**（抽取 claim、实时检索、来源验证、评分——正是 Scout 的证据层） | 需要高准确率的 claim 抽取与时效判断；评测数据要自建 | **首选** |
| **Tavily-02** 会前简报 Agent | 研究 Agent | 中低 | 中（4–5 人日） | 高（实体研究 + 近 30 天新闻 + 引用） | 同质化严重（大量通用 research agent）；差异化弱 | 备选 |

### 单题短评

- **Bifrost-02**：真正的难点不是"跑分"，而是**可复现**与**跨架构适配**。我们的差异化：把"信息新鲜度"和"证据可核验性"作为一等评测维度（大多数 benchmark 只看答案对错），并用统一 Adapter 协议接不同 Agent（HTTP / CLI / Python）。这与 Tavily-01 天然咬合。
- **Tavily-01**：核心是"**claim 级**的时效判断"，而不是"整段答案像不像旧的"。设计要点：claim 抽取 → 时效类型分类（pricing/API version/law/leadership）→ 实时检索 → 来源时间与权威性校验 → Freshness Score + 判定（fresh / stale / uncertain / outdated）+ 证据。评分必须可解释（给出"为什么判 stale"）。
- **Tavily-02**：如果时间不够，这是最容易保底交付的题；但它无法复用我们"验证/冲突"的差异化，且评委见过太多"新闻简报"。
- **Bifrost-01/03/04**：与 Scout 资产重叠低，14 天单人做不出有竞争力的作品；不建议为"两轨都参加"而硬做。

---

## D. 选题建议：Bifrost-02 + Tavily-01（整合）

### D.1 组合对比

| 组合 | 协同性 | 14 天可行性 | 差异化 | 风险 | 结论 |
|---|---|---|---|---|---|
| **B02 + T01（整合）** | **高**：benchmark 的一等指标就是 freshness；detector 是 benchmark 的评分模块 | 中（可裁剪） | **高**：Freshness-aware benchmark 市面上少 | 范围大；需严格 MVP | **推荐** |
| B02 + T02（整合） | 中：benchmark + briefing，两个产品 | 中 | 中 | 故事线散、两个 demo | 备选 |
| T01 + T02（只做 Tavily 两题） | 中 | 高 | 中 | 放弃 Bifrost 现金/面试 | 若只允许一轨时的备选 |
| B01 + T01 | 低 | 低 | 低 | 双线作战 | 不做 |
| B04 + T01 | 低 | 中 | 低 | 网关功能与核验无关 | 不做 |

### D.2 推荐方案（默认）

**项目名**：YAI Scout — *Freshness-aware Research Benchmark*（副标题：Benchmarking research agents on evidence, not vibes）

**一句话**：一个把"研究型 Agent 的答案对不对"与"信息新不新、证据硬不硬"放在同一张榜上的评测平台；榜单里的 freshness 分数由内置的 Stale-answer Detector 实时核验得出。

**两轨映射**：
- **Bifrost-02**：Benchmark Dataset + Agent Adapter 协议 + Runner + 排行榜 + 可复现报告。
- **Tavily-01**：Claim 抽取 → 时效判定 → Tavily 实时检索 → 来源验证 → Freshness Score → 证据展示；既是独立工具，也是 benchmark 的评分模块。

**为什么不是两个独立项目**：官方公告明确允许"combine both challenges into one integrated solution"；整合方案只需一套架构、一次提交、一份 Demo，对 14 天单人最省。若主办方回复"必须两项目"，同一仓库拆两个入口即可（`apps/benchmark`、`apps/detector`），复用 90% 代码。

---

## E. API 与免费资源

| 资源 | 免费额度 | 赛事专属 | 领取/申请 | 备注 |
|---|---|---|---|---|
| **Tavily API** | **1,000 credits/月**（每月 1 日重置），无需信用卡；Dev 100 RPM / Prod 1,000 RPM（Prod 需付费/PAYGO） | 公告：**$60,000 credits 给 top 3 队**；**$8,000 credits 给使用 Tavily 的参与者** | app.tavily.com 注册取 key；赛事 credits 领取方式**未公开** → 问主办方 | 计价：basic 1、advanced 2、extract 5 URL=1–2、map 10 页=1、research 4–250；PAYGO $0.008/credit |
| Tavily 学生计划 | Project 档 4,000 credits/月 × 4 个月 | — | 学生邮箱/证件验证（help.tavily.com） | 官方写明可用于 hackathon |
| **Bifrost** | Apache-2.0 自托管免费（`npx @maximhq/bifrost` / docker，默认 8080） | 未发现赛事 credits；Bifrost 轨现金 **$1,000**（图注 $500/$300/$200）+ 获奖队直通面试 | GitHub / docs.getbifrost.ai | 无托管免费层；**未强制使用**；语义缓存会干扰 freshness 评测，评测时必须关闭 |
| Omnidimension | 免费 20 分钟 | $50 credits ×100（平台页） | omnidim.io | 与本项目无关 |
| 模型 API | 自备 DeepSeek/Claude 等 | — | — | 单份报告成本 ≈$0.06–0.25 |

**Tavily credits 的美元口径**（重要）：官方图注 "Prizes in Tavily credits (USD)"；$30K/$20K/$10K 是**以美元计价的 credits**，不是现金。按 Tavily PAYGO $0.008/credit 反算约 **375 万 / 250 万 / 125 万 credits**——**这只是换算参考，赛事 credits 的实际计价/有效期未公开**，不要写进提交材料。

**日期口径**：HackCulture / Luma（Geek Room & Tavily Events 联合主办）均为 **11/1–11/15**；Tavily 社区页把同一链接标为 **Nov 1–22**。按 11/15 执行。

**两个必须问清的额度问题**：
1. $60K top-3 是每队还是每人？是否可团队共享？有效期多久？
2. $8K "for participants building with Tavily" 是人人有份（如 $65/人）还是按项目评审发放？如何领取？

---

## F. 开发建议（14 天，单人）

### F.1 架构（在现有 G0 上扩展）

```text
YAI Scout — Freshness-aware Research Benchmark
├─ benchmark/                  # Bifrost-02
│  ├─ dataset/                 # 15–20 个研究任务 + 金标答案/证据/as_of
│  ├─ adapter/                 # 统一协议：HTTP / CLI / Python 三种接入
│  ├─ runner/                  # 隔离运行、重试、trace、token/时延/成本采集
│  └─ leaderboard/             # 排名与可复现报告
├─ detector/                   # Tavily-01
│  ├─ claims/                  # claim 抽取 + 时效类型分类
│  ├─ verify/                  # Tavily 实时检索 + 来源校验
│  └─ freshness/               # Freshness Score + 判定 + 证据
├─ scoring/                    # 统一评分：正确率/完成率/陈旧率/引用质量/成本/时延
├─ store/                      # 复用 G0：SQLite + 事件 + 成本台账
├─ api/ + web/                 # 复用 G0：FastAPI + SSE + 控制台（扩展三视图）
└─ kernel/                     # YAI 适配层（v0.25.0，唯一依赖面）
```

数据模型新增：`run`（一次评测）、`agent`（适配器注册）、`task`（benchmark 题）、`answer`、`claim`、`evidence`、`freshness_verdict`、`score`。G0 的 `source`/`event`/`cost` 直接复用。

### F.2 MVP（必须完成的 5 件）

1. **Benchmark 数据集 15 题**：覆盖 pricing / API version / law / leadership / 科研进展五类时效敏感问题；每题有金标答案、证据 URL、as_of。
2. **Adapter 协议 + 2 个适配器**：YAI Scout（我们的 Agent）+ 基线（单轮 RAG）；证明"不同架构可接入"。
3. **Runner + 排行榜**：同一任务跑两个 Agent，记录答案、引用、token、时延、成本；榜单按综合分排序，可下钻。
4. **Stale-answer Detector**：输入任意 LLM 答案 → claim 列表 → 逐条 Tavily 核验 → Freshness Score(0–100) + 判定 + 证据链接；至少覆盖 3 类时效事实。
5. **Dashboard 三视图**：Leaderboard / Task Detail / Claim Evidence；SSE 实时进度；报告可导出。

**砍掉（Should）**：第三个适配器、Bifrost 网关接入、历史趋势图、多语言、账号体系。
**绝不做**：自建爬虫农场、付费墙、实时监控。

### F.3 技术栈

Python 3.12 + FastAPI + SQLite（复用 G0）；Tavily REST（httpx）；DeepSeek/Claude 做 claim 抽取与判定；React 或现有静态控制台扩展；YAI Agent Core 0.25.0 仅作 worker 内核；部署仍用单容器（Render 免费层，注意无持久盘）。

### F.4 开发优先级（P0 → P2）

P0：detector 的 claim 抽取 + 核验 + Freshness Score（Tavily 轨核心）；benchmark runner + 2 适配器 + 榜单（Bifrost 轨核心）。
P1：Dashboard 三视图 + 证据下钻；评分引擎的 6 项指标；Demo 数据。
P2：第三个适配器；Bifrost 网关（缓存关闭）；导出 PDF；历史对比。

### F.5 11/15 倒排（北京时间为准）

| 日期 | 交付 | 门禁 |
|---|---|---|
| 11/01（今天） | 规则确认邮件发出；数据模型扩展；Adapter 协议定稿 | 协议文档 + 邮件已发 |
| 11/02–11/03 | Benchmark 数据集 15 题 v1；Runner 骨架；基线适配器 | 能跑通 1 题 × 2 Agent |
| 11/04–11/05 | Detector：claim 抽取 + 时效分类 + Tavily 核验 | 10 条 claim 的判定可解释 |
| 11/06–11/07 | Freshness Score + 评分引擎；Scout 适配器 | 一份完整 report |
| 11/08–11/09 | Dashboard 三视图 + SSE；榜单 | 端到端可演示 |
| 11/10 | 数据校准 + 错误分析；Demo 数据 | 15 题全跑一遍 |
| 11/11 | 部署 + 预热 + 录屏素材 | 在线 URL 可用 |
| 11/12 | **功能冻结**；README / AI usage / 两轨映射 | 文档齐全 |
| 11/13 | 2.5 分钟视频；提交材料 | 视频可独立看懂 |
| 11/14 | 彩排 + 最终部署 + buffer | 可提交状态 |
| 11/15 12:00 | **提交**（离截止 14.5h） | 收到确认 |

### F.6 Demo 脚本（2.5 分钟）

1. 0:00–0:20 钩子：一句"某 AI 说某 API 每月 $20"，Detector 判 **stale（12/100）**，并给出官方最新价格与日期。
2. 0:20–0:50 同一问题，两个 Agent（Scout vs 基线）跑 benchmark；榜单显示：一个答案"新但错"，一个"对但旧"。
3. 0:50–1:20 下钻 claim：逐条证据、来源、时间戳、freshness 分数与理由。
4. 1:20–1:50 换一个"法律/领导层变动"类问题，展示另一类时效判定。
5. 1:50–2:10 排行榜 + 成本/时延对比：证明"可复现、可比较"。
6. 2:10–2:30 架构一页 + YAI/Tavily 致谢 + 仓库/在线地址。

---

## G. 必须向主办方确认的问题（可直接发邮件）

**收件人**：team@geekroom.co.in
**Subject**：Clarification on Multi-Track Participation, Submission Format and Credits – Geek Room Global AI Hackathon

```
Hi Geek Room team,

I have registered for the Global AI Hackathon as an individual participant (team of 1) and am planning my build around Bifrost-02 + Tavily-01.

I would like to confirm a few points before finalizing the architecture:

1. Track selection: the HackCulture announcement says "Every team must select one problem statement from each track", while the problem-statement graphic says "Pick 1 from either track, or combine one from each". Which is authoritative — must we submit one problem from each track, or may we choose only one track?

2. Submission format: the submission form has a single required GitHub link and only one submission is allowed. How should we submit "two separate projects"? Should both projects live in one repository (with one submission), or are two submissions permitted?

3. If we build one integrated solution covering both tracks, will it be evaluated by both track judges and be eligible for prizes in both tracks?

4. Credits: are the Tavily prizes ($30,000 / $20,000 / $10,000) in USD-denominated credits, per team or per member? What is the expiry/validity period, and how are they claimed? How is the $8,000 participant credit pool distributed?

5. Bifrost: is the $1,000 cash prize split as $500 / $300 / $200, and does the interview opportunity apply to all members of winning teams?

6. Is there a per-team submission limit, and can the submission be updated before the 15 Nov deadline?

Thank you!
```

> 若 24 小时内没有回复：在官方 WhatsApp 群（`https://chat.whatsapp.com/GkRxNNSAhBP0y89HG8SGpa`）与 Discord 同步问一遍，并**默认按"两轨整合项目 + 单仓库单提交"执行**（对两种口径都安全）。

---

## H. 证据、方法与局限

### H.1 证据等级

| 等级 | 来源 | 用途 |
|---|---|---|
| 一级（官方平台数据） | `https://api.hackculture.io/api/v1/hackathon?slug=ai-global-hackathon`（原始 JSON 已存档 `research/problem-statements/hackculture-event.json`） | 时间线、报名状态、提交表单字段、奖项配置、公告原文 |
| 一级（官方页面） | https://hackculture.io/hackathons/ai-global-hackathon ；https://geekroom-mu.vercel.app/event/global-ai-hackathon | 规则、资格、FAQ（注意 Themes/Prizes 区未同步） |
| 一级（官方公告/帖） | 平台公告（10/31 17:13Z）；官方 LinkedIn：https://www.linkedin.com/feed/update/urn:li:activity:7522343349710946304 ；官方 X @geek__room_ | 题目发布、奖金、双赛道说明 |
| 一级（联合主办页） | https://luma.com/33nivwqh （Geek Room & Tavily Events 联合主办，Nov 1–15） | 日期、联合主办确认 |
| 二级（Tavily 社区页） | https://www.tavily.com/community | 列出本赛事（标注 Nov 1–22，与 HackCulture 冲突） |
| 二级（官方图片转述） | 官方赛题图（核查员读取） | 题目分类、$30K/$20K/$10K、$500/$300/$200、3 winners、Bifrost priority |
| 二级（合作方官方） | docs.tavily.com、tavily.com/pricing、docs.getbifrost.ai、github.com/maximhq/bifrost | 额度、限流、许可证、部署 |
| 三级（二手） | that.promo、Instagram、LinkedIn 个人帖 | 仅线索，不作为规则依据 |

### H.2 局限（如实说明）

- **LinkedIn 帖子未能直读**（地区限制 451）；**Discord 公告需登录**（API 401），未读取；**X 不可达**。因此"官方赛题图"的具体措辞来自核查员读取，未能逐字比对原图；题目标题的逐字比对已由另一路核查完成（6/6 一致）。
- HackCulture Themes 区与 Prizes 区**未同步**（Themes 仍 REVEALING SOON，theme API 返回 `[]`；Prizes 仍为 $65×100 的旧配置），与 10/31 公告冲突；本报告以公告 + API 配置为准。
- **Tavily 社区页把同一赛事标成 Nov 1–22**，与 HackCulture/Luma 的 11/15 冲突；按 11/15 执行。
- 官方未公布：双赛道评分 rubric、评委名单、提交是否可修改、两轨是否分别评奖、credits 领取与有效期、面试具体形式、"两个独立项目"在单次提交里的具体形态。
- 结论中所有 **[推断]** 已显式标注；未标注者均来自上表一级/二级来源。

---

*本报告只做调查与规划，未创建收费资源、未修改 YAI 主仓库、未进行任何提交。*
