# API 与资源成本评估（双项目）

> 核对时间：2026-11-01 11:30（UTC+8）。所有数字带来源；查不到写「需确认」，不编造。

## 1. Tavily（Project B 的检索命脉，Project A 的 evidence 可选）

| 项目 | 事实 | 来源 |
|---|---|---|
| Endpoints | `/search`、`/extract`、`/map`、`/crawl`、`/research` | docs.tavily.com |
| 免费额度 | **1,000 credits/月**（每月 1 日重置，无需信用卡） | https://docs.tavily.com/documentation/api-credits |
| 计费 | basic search 1；advanced 2；extract 每 5 URL 1（basic）/2（advanced）；map 每 10 页 1；research 动态 4–250 | 同上 |
| 限流 | Dev key 100 RPM；Production 1,000 RPM（需付费/PAYGO） | https://docs.tavily.com/documentation/rate-limits |
| PAYGO | **$0.008/credit** | 同上 |
| 学生计划 | Project 档 4,000 credits/月，免费 4 个月，官方写明可用于 hackathon | help.tavily.com |
| 赛事额度 | 公告：Tavily **$60,000 计价 credits 给 top 3**；**$8,000 credits 给使用 Tavily 的参与者** | 平台公告（10/31） |
| 领取/有效期 | **未公开** → 已列入追问邮件 | — |
| 当前 key | 已配置（`.env`），`/api/healthz` 显示 `mode=key, authenticated=true`；冒烟调用正常 | 本地验证 2026-11-01 |

**成本模型（每份 Freshness 报告，6 条 claim）**：6 次 basic search ≈ **6 credits**；若每条取 2 次（补搜）≈ 12 credits。按 1,000/月免费额度，可跑 **~80–160 份报告/月**。

**成本模型（一次 Benchmark）**：15 题 × 3 Agent × 1 次检索 = 45 credits；若每条答案再做 2 条 claim 的 freshness 核验，再加 90 credits ≈ **135 credits/次**。开发期跑 10 次 ≈ 1,350 credits → 需学生计划或小额充值；demo 用 3 题 × 3 Agent 控制成本。

## 2. Bifrost（Project A 的"对网关友好"展示，可选）

| 项目 | 事实 | 来源 |
|---|---|---|
| 许可证 | **Apache-2.0** | GitHub API / LICENSE |
| 自托管 | `npx @maximhq/bifrost` 或 `docker run -p 8080:8080 maximhq/bifrost`；默认 8080 | https://docs.getbifrost.ai/overview |
| 能力 | 多 provider OpenAI 兼容、自动 fallback、负载均衡、语义缓存、virtual key/预算、MCP gateway、Prometheus/OTel | 同上 |
| 免费托管 | **未发现**（OSS 自托管免费；企业版收费） | 同上 |
| 赛事要求 | **未强制使用**；仅作为 "Build Resources" 技术资源 | 赛事 Rules §7 |
| 赛事 credits | **未发现** | — |

**用途**：Benchmark 里作为"模型网关"层可做两件事：① 多模型 failover（演示鲁棒性）；② 成本/延迟对比（Bifrost overhead）。
**注意**：评测公平性要求**关闭语义缓存**（缓存会绕过 provider，污染结果），并记录网关开销。

## 3. 模型 API

| 项目 | 事实 | 来源 |
|---|---|---|
| 已给 base_url | `https://api.suanli.cn/v1`（OpenAI 兼容） | 用户提供 |
| DeepSeek key | **缺失**：用户提供的第二串与 Tavily key 相同，`/v1/models` 返回 401 | 本地验证 |
| 价格量级 | DeepSeek V4.1-Flash 高峰 $0.30 输入 / $1.20 输出（每百万 token）；Claude Haiku 5.5 $0.10/$0.50 | 官方定价页（2026-10-31 核对） |

**成本估算**：
- Freshness 报告：claim 抽取 3K in / 0.8K out；关系判定 2K in / 0.3K out × 6 条 ≈ 15K in / 3K out ≈ **$0.009/份**（Flash 高峰）。
- Benchmark：每题答案生成 2K/0.5K × 15 题 × 3 Agent ≈ 90K in / 22K out ≈ **$0.053/次**。
- 14 天开发 + 评测 ≈ **$3–8**。

## 4. 现金预算（双项目，14 天）

| 项目 | 用量假设 | 成本 |
|---|---|---|
| Tavily | 免费 1,000 + 学生计划（若可用） | $0 |
| Tavily 备用充值 | 1,500 credits（仅缺口时） | ≤$12 |
| 模型 API | 开发 + 评测 + demo | ≤$10 |
| 部署 | Render 免费层 / 本地 Docker | $0 |
| 域名/素材 | 平台子域 + 开源字体 | $0 |
| **合计** | | **≤ $22**（目标 ≤$20，优先用学生计划） |

## 5. 待确认

1. 赛事 Tavily credits 的领取方式、有效期、是否每队/每人。
2. $8,000 参与者 credits 的分配规则。
3. Bifrost 是否有赛事专属额度（目前未发现）。
4. suanli.cn 的实际模型名与计费（拿到 DeepSeek key 后确认 `/v1/models` 列表）。
