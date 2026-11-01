# 外部 Agent 接入示例（scout-adapter/1.0）

```powershell
# 1) 启动示例 Agent（离线，无需 key）
.\.venv\Scripts\python.exe -m uvicorn examples.echo_agent:app --port 9101

# 2) 让 Scout 知道它
$env:HTTP_AGENT_URL = "http://127.0.0.1:9101"
# 或调用 API 时显式传：
# POST /api/benchmark/run {"agent_ids":["external_http"],"task_ids":["b_tavily_free_credits"]}
```

## 协议要点

- `GET /manifest` → `{protocol_version, agent_id, agent_version, framework, models, tools, capabilities}`
- `POST /run` → `{protocol_version, run_id, task:{task_id,question,target_time,category}, execution:{deadline_s,max_tokens,tools_allowed,budget_usd}}`
- 响应：`{answer, citations, usage:{prompt_tokens,completion_tokens,model,provider}, cost:{estimated_usd,price_table_version,estimated}, latency_ms, trace, error}`

## 说明

- 示例 Agent 故意不用 Tavily/LLM，证明"不同实现"可被公平评测。
- 真实接入通常需要 30–80 行 adapter/wrapper；我们不承诺"零改代码"。
- 评测时会记录 Agent 的模型/工具配置，避免把配置优势误认为架构优势。
