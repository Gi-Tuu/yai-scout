# 事实核查与 API 预算底稿

> 核查时间：2026-10-31（UTC+8）。方法：官方页面两次独立抓取比对 + 平台条款 + 搜索引擎二手信息交叉验证；官方原文优先。用于支撑 `docs/charter.md` 第 1、4.6、8 节的数字，**未公开项一律标注**。

## 1. 赛事事实

| 项目 | 事实 | 来源 |
|---|---|---|
| 名称 | Geek Room — Global AI Hackathon（Build Globally. Ship Boldly.） | https://geekroom-mu.vercel.app/event/global-ai-hackathon |
| 承办 | HackCulture 平台（报名/提交入口） | https://hackculture.io/hackathons/ai-global-hackathon |
| 时间 | 2026-10-09 → 2026-11-29，全程线上、全球开放 | 同上 |
| 团队 | 1–4 人；个人允许；一人一队；每队 1 件作品 | Eligibility / Rule 4 / Rule 8 |
| 资格 | 任何国家/背景/技能；无学历经验要求 | Eligibility |
| 年龄 | 赛事页未写；平台条款 18+，13–18 需监护人/学校同意，<13 禁止 | https://hackculture.io/legal/terms-and-conditions |
| 报名截止 | 2026-11-15 23:59 IST | Schedule |
| 题目公布 | 2026-11-01 00:00 IST（同时开启提交窗口） | Schedule / FAQ |
| 提交截止 | 2026-11-15 23:59 IST | Schedule |
| 评审 | 2026-11-29 19:00–23:59 IST（约 5h，线上） | Schedule |
| 时区 | 页面明确 IST（UTC+5:30） | 页面头部 |
| 赛道 | 未公布（"REVEALING SOON"） | Themes |
| 合作方 | Bifrost(Maxim AI)=Title/Track；Tavily(Nebius)=Track；Omnidimension/Pathway=Community | Partners |
| 强制项 | 必须加入官方 Discord（Rule 3）；无强制使用合作方 API | Rule 3 / Rule 7 |
| 提交物 | 可运行项目/演示、源码/仓库、项目描述、问题说明、技术栈、AI 使用说明、Demo 视频（if required） | Rule 7 |
| 评审维度 | Innovation / Technical execution / Problem & impact / Use of AI / UX / Scalability（无权重） | Rule 10 |
| 原创性 | 必须原创或有权使用；核心须赛期内开发；库/框架/boilerplate 可用 | Rule 1 / Rule 5 |
| IP | 参赛者保留所有权；平台获非独占免费许可 | 平台条款 |
| 奖项 | 总奖池 $11.5K；现金 $1,000；Tavily credits $65×100；Omnidimension $50×100；证书 | Prizes |
| 奖池口径 | 官方写 "$11.5K prize pool, including $1,000 cash"；但 credits 名义值 100×$65 + 100×$50 = $11,500，再加 $1,000 现金 = $12,500 → **官方口径不自洽，无法确认构成**；材料中不引用 | 官方原文 + 算术 |

## 2. 北京时间换算（关键）

| 事件 | IST | 北京时间 |
|---|---|---|
| 题目公布 / 提交开启 | 11-01 00:00 | **11-01 02:30** |
| 报名 / 提交截止 | 11-15 23:59 | **11-16 02:29** |
| 评审窗口 | 11-29 19:00–23:59 | **11-29 21:30 – 11-30 02:29** |

## 3. 未公开 / 需确认

1. 正式题目与赛道划分（11/1 公布）。
2. 评审权重、评分表、评委名单。
3. 提交平台与表单字段（报名页需登录）。
4. API credits 的领取方式与条件（官方页 "100 winners" 与 "all participants" 自相矛盾）。
5. Demo 视频是否必需/时长/格式。
6. 评审 5h 窗口内的答辩形式。
7. Tavily 查询数据保留期（隐私页未写）。
8. Bifrost 是否有免费托管/赛事额度；Serper 单价。

## 4. 二手信息冲突

- 早期宣传：$5,000 prize pool、$100 Tavily credits；官方现行页：$11.5K、$65 credits → **以官方页为准**，提交材料不引用具体奖金。
- Discord 邀请 https://discord.gg/WBvcRKg8t 实测有效，**有效期至 2026-11-08**（早于截止，需尽早入群）。
- 官方报名卡时间戳 "08 Oct 11:43 AM" 与事件头 "Oct 9" 不一致（建页时间），以正文日期为准。

## 5. API 额度与价格（2026-10-31）

### Tavily
- 免费 1,000 credits/月，无需信用卡，每月 1 日重置；Dev key 100 RPM，Production 1,000 RPM（需付费/PAYGO）。
- 计费：basic search 1、advanced 2；extract basic 每 5 URL 1、advanced 每 5 URL 2；map 每 10 页 1（带 instructions 2）；crawl = map + extract；research 动态 4–250 credits。
- 付费：PAYGO $0.008/credit；Project $30=4,000；Bootstrap $100=15,000；Startup $220=38,000；Growth $500=100,000。
- 学生计划：Project 档免费 4 个月（4,000 credits/月），官方写明可用于 hackathon（help.tavily.com）。
- 返回字段：title/url/content/score/raw_content/published_date/favicon/images/id；顶层 usage.credits。
- 来源：https://docs.tavily.com/documentation/api-credits ；https://docs.tavily.com/documentation/rate-limits ；https://docs.tavily.com/documentation/api-reference/endpoint/search

### 合作方
| 合作方 | 额度 | 来源 |
|---|---|---|
| Bifrost (Maxim AI) | Apache-2.0，自托管免费；20+ provider，OpenAI 兼容，failover/语义缓存/virtual key/MCP gateway；企业版收费 | https://github.com/maximhq/bifrost ；https://docs.getbifrost.ai/overview |
| Omnidimension | 免费 20 分钟；Starter $20/月=317 分钟 | https://omnidim.io/pricing |
| Pathway | BSL 1.1（非 OSI）；Community 免费至 8GB/4 核，需 license key | https://pathway.com/pricing |

### Fallback 检索
Brave $5 credits/月；Exa $10/月；Firecrawl 1,000 credits/月；Jina Reader 100 RPM；Semantic Scholar 共享限速；PubMed 3 req/s（key 10）；arXiv 免费。

### 模型价格（USD / M token）
| 模型 | 输入 | 输出 | 上下文 |
|---|---|---|---|
| DeepSeek V4.1-Flash | $0.30 高峰 / $0.15 低谷 | $1.20 / $0.60 | 1M |
| DeepSeek V4-Pro | $1.32 / $0.66 | $3.96 / $1.98 | 1M |
| Claude Haiku 5.5 | $0.10 | $0.50 | 长上下文另计价（具体窗口需确认） |
| Claude Sonnet 5.5 | $2 | $10 | 1M |
| Qwen3.8-Max | $1.65 | $4.95 | 1M |
| Qwen3.7-Flash | $0.03–0.20 | $0.13–0.80 | 1M 分档 |

来源：https://api-docs.deepseek.com/quick_start/pricing ；platform.claude.com/docs/en/about-claude/pricing ；alibabacloud.com/help/en/model-studio/model-pricing

## 6. 100 份报告预算（每份 6 子问题，150K in / 15K out）

| 档位 | Tavily credits | Tavily 成本 | LLM 成本（Flash 高峰） |
|---|---|---|---|
| 精简（10 basic + 4 advanced + 25 extract） | 23/份 → 2,300 | 免费不够；PAYGO $18.4；Project $30 | ≈$6.3 |
| 重度（30 basic + 5 advanced + 40 extract） | 48/份 → 4,800 | PAYGO $38.4；Project $30 + $6.4 | ≈$6.3 |

结论：15 个日历日开发期约 50 次开发 run + 14 次 smoke + 25 次评测 + 16 次基线 + 3 次盲测 ≈ **2,300–2,600 credits**；免费 1,000 + 一次性 $13 充值（1,600）可覆盖；有学生计划则 $0。

## 7. YAI Agent Core 基线（详见 `research/yai-interface-audit.md`）

- 版本 v0.25.0；PyPI 0.25.0 对应 tag `v0.25.0` → `614f3106c7237b8bee662b925748b56c4da6d890`；审计时仓库 HEAD 为 `ce4773d6...`（tag 后 4 个提交，含 pypdf 升级，**非** v0.25.0）；MIT；Python ≥3.11；内核零第三方硬依赖。
- 依赖方式：`yai-agent-core==0.25.0` + extras `[llm,server,openapi,mcp,otel]`；`uv.lock` 锁定；`docs/dependencies.md` 记录。
- 不可依赖：`build_spec` 的 pydantic 参数、`MemoryVault` 当证据库、`evaluation` 当质量门、FastAPI battery 当主服务。
