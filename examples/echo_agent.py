"""示例外部 Agent：实现 scout-adapter/1.0，用于证明跨架构接入。

启动：
    .\.venv\Scripts\python.exe -m uvicorn examples.echo_agent:app --port 9101

接入 Benchmark：
    $env:HTTP_AGENT_URL="http://127.0.0.1:9101"
    （或调用 /api/benchmark/run 时显式传 agent_ids=["external_http"]）
"""

from __future__ import annotations

from fastapi import FastAPI

from yai_scout.benchmark.protocol import (
    PROTOCOL_VERSION,
    AdapterCost,
    AdapterManifest,
    AdapterRunRequest,
    AdapterRunResponse,
    AdapterUsage,
)

app = FastAPI(title="Echo Agent (external, scout-adapter/1.0)")

# 故意不用 Tavily/LLM：证明"不同实现"也能接入；答案固定，便于评测对比。
ANSWERS = {
    "tavily": (
        "Tavily 免费计划每月 1,000 API credits [1]。",
        ["https://docs.tavily.com/documentation/api-credits"],
        "1000",
    ),
    "bifrost": (
        "Bifrost 使用 Apache-2.0 许可证 [1]。",
        ["https://github.com/maximhq/bifrost"],
        "Apache-2.0",
    ),
    "yaimodel": (
        "YAI Agent Core 当前版本是 0.25.0 [1]。",
        ["https://github.com/Gi-Tuu/yai-agent-core"],
        "0.25.0",
    ),
}


@app.get("/manifest")
async def manifest() -> dict:
    return AdapterManifest(
        agent_id="echo-agent",
        agent_version="0.1.0",
        framework="custom",
        models=[],
        tools=[],
        capabilities={"streaming": False, "claims": False, "trace": True},
        contact="demo@example.com",
    ).model_dump()


@app.post("/run")
async def run(request: AdapterRunRequest) -> dict:
    question = request.task.question.lower()
    answer, citations, value = "", [], ""
    for key, payload in ANSWERS.items():
        if key in question:
            answer, citations, value = payload
            break
    if not answer:
        answer = "I cannot verify this from my (offline) knowledge."
    return AdapterRunResponse(
        protocol_version=PROTOCOL_VERSION,
        answer=answer,
        citations=citations,
        usage=AdapterUsage(
            prompt_tokens=0,
            completion_tokens=0,
            model="offline-echo",
            provider="local",
        ),
        cost=AdapterCost(estimated_usd=0.0, price_table_version="n/a", estimated=False),
        latency_ms=1,
        trace=[{"step": "offline-lookup", "value": value}],
    ).model_dump()

