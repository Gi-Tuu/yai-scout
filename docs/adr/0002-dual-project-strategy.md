# ADR-0002：双赛道、双独立作品、共享技术底座

- 状态：**Accepted**（2026-11-01）
- 取代：`ADR-0001`（整合项目方案，已废弃）
- 相关：`research/organizer-reply.md`、`docs/hackathon-rules-report.md`

## 背景

主办方 2026-11-01 邮件回复 **"All yes."**，确认：
1. 同一参赛者/团队可同时参加 Bifrost 与 Tavily 两轨；
2. 可提交两个独立项目（一轨一个）；
3. 一个整合项目也可同时接受两轨评审。

参赛者决定采用 **双作品、共享底层、独立交付**，不再做"一个整合项目"。

## 决策

1. **Project A：YAI Scout Benchmark** —— 参加 Bifrost Track / Problem 02（AI Agent Benchmarking Platform）。
2. **Project B：YAI Scout Freshness** —— 参加 Tavily Track / Problem 01（Stale-answer Detector）。
3. 两者共享 **YAI Scout Core**（Adapter 协议、数据集、证据引擎、来源管理、评测基础设施、执行轨迹、存储）。
4. 两个项目各自具备：独立产品定位、独立 README/参赛说明、独立 Demo 入口、独立测试与验收、独立提交材料。
5. 仓库组织：**monorepo**（一个仓库、`apps/benchmark` 与 `apps/freshness` 两个入口 + `packages/scout_core`）；若平台要求两个 GitHub 链接，再拆两个薄仓库（代码仍从 monorepo 同步）。

## 后果

- 正面：两轨都满足；共享层只写一次；两个 Demo 可分别讲清楚。
- 负面：工作量约为单项目的 1.6–1.8 倍；共享层可能成为瓶颈；提交材料要做两份。
- 缓解：先冻结共享层接口（11/02），再并行开发两个 app；共享层只做"两项目都真正需要"的能力；设 11/12 功能冻结。

## 不做什么

- 不做三个提交（两作品 + 整合）。
- 不为"形式独立"复制两套公共组件。
- 不修改 YAI Agent Core 主仓库。
