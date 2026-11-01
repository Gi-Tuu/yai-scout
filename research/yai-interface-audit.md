# YAI Agent Core 接口审计（供 YAI Scout 技术选型）

只读审计 `E:\Competition\YAI Agent Core`。每条结论标注 `文件:行号`；`build_spec` 的 pydantic 行为为本地实跑验证，其余均来自源码与文档。

## 0. 版本与许可证

- v0.25.0，commit `ce4773d67c6ee658c32c6559c91d02aa10dab18d`（2026-10-31），MIT，`requires-python>=3.11`。
- 内核零第三方硬依赖：`dependencies = []`（pyproject.toml:21），13 个 extras（pyproject.toml:30-78），AST 级守门测试见 docs/IMPLEMENTATION_STATUS.md:53。
- PyPI `yai-agent-core` 已发布 0.25.0（wheel 342 KB / sdist 4.2 MB）；仓库内 `dist/` 只有 0.8.0，不是发布源。

## 1. 可直接复用的接口

| 能力 | 入口符号 | 文件:行 | 稳定性 | Scout 怎么用 |
|---|---|---|---|---|
| 门面 / 运行 | `AgentCore`、`run()`、`astream()`、`AgentCore.auto()` | core.py:80 / 568 / 486 / 375 | 稳定公共契约 | 每个检索会话一个实例（实例内串行） |
| 事件与结果 | `AgentEvent`、`EventType`、`RunResult` | types.py:1143 / 29 / 1150 | 稳定 | 按 `type` 枚举过滤，构建进度面板 |
| 工具声明 | `ToolSpec`、`build_spec`、`ToolRegistry` | types.py:733、discovery/introspect.py:147、tools/registry.py:18 | 稳定 | 检索 / 抓取 / 抽取工具注册 |
| 模型契约 | `ModelProvider.achat`（`tier` 分档） | spi/model.py:11-43 | 稳定 SPI | 实现自己的检索摘要模型或换后端 |
| 现成后端 | `ScriptedModel`、`OpenAICompatProvider`、`AnthropicProvider` | llm/scripted.py:24、llm/openai_compat.py:12、llm/anthropic.py | 稳定 | 离线回归用 Scripted，线上用兼容后端 |
| 预算熔断 | `Budget`、`BudgetExceeded` | kernel/budget.py:66 / 37 | 稳定 | 每任务封顶 model/tool calls |
| 评测指标 | `collect_trace`、`score_task`、`aggregate` | evaluation/scoring.py:59 / 138 / 247 | 稳定（开发工具） | 复用"工具精确/召回、越权、无支撑断言"口径 |
| 嵌入 SPI | `EmbeddingProvider.embed_texts` | spi/embedding.py:28-39 | 稳定 SPI | 接 Scout 自己的向量索引 |
| MCP 客户端 | `attach_mcp_tools`、`McpToolBridge` | integrations/mcp/client.py:174 / 91 | 稳定 | 把检索服务当 MCP Server 接入 |
| OpenAPI 桥 | `attach_openapi_tools`、`OpenApiSpecConfig` | integrations/openapi/client.py:233、spec.py:21 | 稳定 | 把文献 API 变成工具（`read_only`/`prefix`） |
| 追踪 | `traced_run`、`traced_astream` | integrations/tracing/otel.py:236 / 204 | 稳定 | 外侧订阅，不改内核 |
| HTTP 骨架 | `create_app` | batteries/fastapi_server/app.py:50 | 半稳定（battery） | 仅作参考，不建议当 Scout 主服务 |

## 2. 需要适配 / 包装的接口

1. **pydantic 参数不支持**：`build_spec` 只映射内置类型与容器（introspect.py:29-115）。实测 `def f(q: Quote)`（BaseModel）生成 `{"q":{"type":"string"}}`，真实调用必被入参校验拒绝。→ 自己 `ToolSpec(input_schema=Model.model_json_schema(), handler=fn)` 并让 handler 收 dict。
2. **无 token 级流式**：`achat` 一次返回 `ModelResponse`（spi/model.py:29-43）；`astream` 是**事件**流（core.py:486）。长报告逐字输出需 Scout 自己实现。
3. **系统提示词不可注入**：`_SYSTEM_TEMPLATE` 是模块常量（loop.py:71，使用点 loop.py:471）。研究人设、引用规范只能用 `register_state_provider`（瞬态 system 块，不进历史，core.py:386-399）或工具包装。
4. **计划无结构化表示**：`_make_plan` 用正则抽编号（loop.py:760），`plan_created.data["steps"]` 无 id/状态/依赖；`replan` 覆盖式重写并发 `plan_revised`（meta_tools.py:240-325，事件字段仅 `revision/reason/steps`）。多轮证据链须 Scout 自建。
5. **`RunResult` 信息量小**：只有 `strategy/events/final_text`（types.py:1150-1153），无 run_id、usage、cost；预算快照只在 `DONE.data["budget"]`（loop.py:568-580）。
6. **上下文预算写死**：`Context(max_chars=24000)`（context.py:53）无对应 `AgentCore` 参数；长报告需开 `context_compaction` 并调 `tool_result_char_limit`（默认 16000，executor.py:59；裁剪为头+尾+显式省略标记，executor.py:81-111，绝不静默删）。
7. **单实例串行**：`_task_lock`（core.py:152 / 510）。并发检索请多实例共享 model/sandbox。`DONE` 之后还有学习回灌，消费者提前 `break` 会跳过（core.py:504-506）。
8. **"声明即约束"只在执行器**：`governance.timeout_ms` 取全局/工具更严一档（executor.py:253-265），`rate_limit` 超限不进 handler（executor.py:565），权限闸同处；**同步 handler 超时无法中断**（executor.py:320-338）。
9. **取消与超时各自设点**：模型调用 `model_timeout` 默认 60s（loop.py:123）、工具 `tool_timeout`、路由分类 15s（router.py:105）、委派子员工 60s；取消靠 `task.cancel()` 或关闭 `astream`，`CancelledError` 一律向上传播（loop.py:547-548），收尾用 `aclose(close_shared=)`（core.py:296-337）。
10. **委派不在 wheel**：`shell/employee` 仅进 sdist（pyproject.toml:85 wheel 只打 `src/yai_core`）。`run_worker`（worker.py:215）限制 `MAX_DEPTH=2`、`MAX_CONCURRENT=5`（worker.py:31-33），默认白名单靠工具名前缀 `list_/get_/search_…` 猜（worker.py:60-63），子员工 `llm_router=False`、无发现源（worker.py:169-179）。
11. **FastAPI battery 偏运维**：仅 6 个端点（health / verification / readyz / metrics / tools / POST run，app.py:166-209）；`/v1/agent/run` 一次性返回全部事件、无 SSE；默认 `CollectChannel` 自动确认（channels/collect.py:9），clarify 会拿到空回答。

## 3. 不建议依赖的部分

- **内置记忆当证据库**：`MemoryVault` 每次召回全量扫描 + JSON 整文件原子重写（vault.py:256-338），无 BM25、无 FTS、无增量索引；适合会话级偏好，不适合万级证据。
- **`SqliteStore`**：只实现 `history` / KV（sqlite_store.py:241-434），无向量/全文检索。
- **`evaluation` 当质量门**：golden 只有 5 条（scripts/eval_tasks.py）；unsupported claim 判定是"凭证子串是否出现在成功结果 preview 里"（scoring.py:131-175），必要不充分信号，不宜对外称"幻觉率"。
- **多智能体编排、分布式限流、内置向量库、MCP Server**：文档明确不做（IMPLEMENTATION_STATUS.md:97-101）。
- `shell/desktop`（PySide6）、`sidecar` 与 Scout 无关；代码工具沙箱内核只定义 `ToolSandbox` 契约。

## 4. 依赖方式建议

- **首选 PyPI 钉死**：`yai-agent-core==0.25.0`，extras `[llm,server,openapi,mcp,otel]`；需解析 PDF 加 `office`，离线向量加 `local-embed`。
- **要委派/薄壳源码就钉 commit**：`yai-agent-core @ git+https://github.com/Gi-Tuu/yai-agent-core.git@ce4773d67c6ee658c32c6559c91d02aa10dab18d`（sdist 含 `shell/`），或把 `shell/employee/{delegate,worker}.py`（约 520 行）vendored 进 Scout。
- 注意既有上界：`anthropic>=0.40,<2`、`mcp>=2.0,<3`（pyproject.toml:37 / 45）。
- **离线/在线切换**：注入不同 `ModelProvider` 即可；`llm_router="auto"` 只在后端声明 `yai_live_router` 时启用 LLM 分类，脚本模型自动走规则（core.py:353-357）。

## 5. 待确认问题清单

1. `shell/employee`（delegate/worker）是否算对外契约？不在 `__all__`、不在 wheel，却写进 README 卖点。
2. v0.26 是否真的翻转 `auto_approve_tools` 默认值（CHANGELOG v0.25.0 "Added" 段称计划先 DeprecationWarning 再翻转）？
3. 0.x 期无公开的 API 弃用政策；约 3 周内 0.8→0.25、2026-09 以来 471 次提交，`ToolSpec`/`ToolGovernance` 仍持续加字段（v0.25 新增 `egress_text`，types.py:432）。
4. MCP 是否只支持 Streamable HTTP + stdio（client.py:132-142 仅三态），旧 SSE 端点是否可用需实测。
5. 检索场景工具多时，`full_schema_budget=24`（core.py:103）会被击穿而触发两次额外模型调用做 schema 聚焦（loop.py:782-839），成本需实测。
