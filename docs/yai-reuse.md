# YAI Agent Core 复用清单与许可证核对

> 核对时间：2026-11-01 11:30（UTC+8）｜核对对象：`E:\Competition\YAI Agent Core` 与 GitHub `Gi-Tuu/yai-agent-core`

## 0. 版本与许可证（先纠一个事实）

| 项目 | 核对结果 | 证据 |
|---|---|---|
| 最新发布 | **v0.25.0**（2026-10-31 publish） | GitHub Releases API `tag_name=v0.25.0` |
| tag commit | `614f3106c7237b8bee662b925748b56c4da6d890` | GitHub Tags API |
| 本地 HEAD | `ce4773d67c6ee658c32c6559c91d02aa10dab18d`（tag 后 4 个提交，仅 docs/uv.lock） | `git log -1` |
| 许可证 | **MIT** | 根 `LICENSE`（1063 字节 / 21 行）+ GitHub API `license.spdx_id = MIT` |
| 仓库内其它 LICENSE | **无**（`.venv` 里的 AGPL/LGPL 文本来自第三方包，不属于 YAI） | 递归查找（排除 `.venv`/`.git`） |

> ⚠️ **与任务说明的冲突**：任务书写"遵守 YAI 的 AGPL-3.0-only 许可证"，但 v0.25.0 的实际许可证是 **MIT**。我们按**事实（MIT）**执行：保留版权与许可声明、在 `NOTICE` 中注明来源与 commit，不引入 copyleft 义务。
> 若你指的是另一个仓库（例如某个 AGPL 分支），请告知仓库地址；在确认前不做 AGPL 假设。

## 1. 复用边界（原则）

- YAI 只作为**可选执行内核/参考 Agent**，不是两个参赛产品的运行时硬依赖。
- 两个产品（Benchmark / Freshness）在**没有 YAI 的情况下也能独立运行**（YAI 只影响"YAI 参考 Agent"这一个 Adapter）。
- 不修改 YAI 主仓库；只通过 `yai-agent-core==0.25.0` 依赖使用；所有调用集中在 `packages/scout_core/kernel/yai_adapter.py`。

## 2. 复用清单

| YAI 能力 | 入口符号 | 用在哪 | 复用方式 | 风险 |
|---|---|---|---|---|
| Agent 运行时 | `AgentCore` / `run` / `astream` | Benchmark 的 YAI 参考 Agent；Freshness 可选的多步核验 worker | 直接实例化，一个会话一个实例 | 0.x API 漂移 |
| 工具调用 | `ToolSpec` / `ToolRegistry` / `build_spec` | 给参考 Agent 注册 search/verify 工具 | 手写 `input_schema`（pydantic 参数有坑） | 低 |
| 模型适配 | `ModelProvider.achat` / `OpenAICompatProvider` | 统一模型入口、离线 `ScriptedModel` | 通过 SPI 注入 | 无 token 流 |
| MCP / OpenAPI | `attach_mcp_tools` / `attach_openapi_tools` | 可选：把外部证据源接成工具 | 懒加载 extra | `mcp>=2,<3` 上界 |
| 预算/事件 | `Budget` / `AgentEvent` / `EventType` | 参考 Agent 的成本与轨迹 | 复用事件语义，映射到 Scout `trace` | 事件是 dict |
| 离线测试 | `ScriptedModel` | 契约测试 / CI 离线跑 | 直接使用 | 无 |
| 评测思想 | `evaluation/` 的指标口径 | Benchmark 指标命名参考 | **借鉴定义，不复用实现**（只有 5 条 golden） | 低 |

## 3. 明确不复用

| 能力 | 原因 | Scout 自研替代 |
|---|---|---|
| 内置 Planner（正则抽步骤） | 无结构化 step/状态/依赖 | `scout_core/dataset` + 自有 plan schema |
| `MemoryVault` 当证据库 | 全量 JSON + 暴力余弦，无 FTS | SQLite + FTS5 + 证据表 |
| `SqliteStore` | 只有 history/KV | 自有 store（run/task/claim/evidence） |
| FastAPI battery | 无 SSE、运维向 | 自有 FastAPI 应用 |
| 子员工委派（`shell/employee`） | 不在 wheel，且我们自控并发 | `asyncio.Semaphore` |

## 4. 版本与升级策略

- 钉 `yai-agent-core==0.25.0`，`uv.lock` 锁定；`NOTICE` 记录 tag SHA `614f3106...`。
- 升级需：改 pin → 跑 `tests/contract/` + 两个产品的 smoke → 更新本文件。
- 不把 YAI 的内部模块 import 进业务代码；只经 `yai_adapter.py`。
