"""Agent Adapter 协议（scout-adapter/1.0）的 Pydantic 契约与校验。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "scout-adapter/1.0"


class AdapterManifest(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    agent_id: str
    agent_version: str = "0.0.0"
    framework: str = "custom"
    models: list[dict[str, str]] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    contact: str = ""


class AdapterTask(BaseModel):
    task_id: str
    question: str
    target_time: str
    category: str = "time_sensitive"


class AdapterExecution(BaseModel):
    deadline_s: int = 120
    max_tokens: int = 4000
    tools_allowed: list[str] = Field(default_factory=list)
    budget_usd: float = 0.05


class AdapterRunRequest(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    run_id: str
    task: AdapterTask
    execution: AdapterExecution = Field(default_factory=AdapterExecution)
    eval: dict[str, Any] = Field(default_factory=dict)


class AdapterUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""


class AdapterCost(BaseModel):
    estimated_usd: float | None = None
    currency: str = "USD"
    price_table_version: str = ""
    estimated: bool = True


class AdapterRunResponse(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    answer: str
    citations: list[str] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    usage: AdapterUsage = Field(default_factory=AdapterUsage)
    cost: AdapterCost = Field(default_factory=AdapterCost)
    latency_ms: int = 0
    trace: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


def validate_run_request(payload: dict[str, Any]) -> AdapterRunRequest:
    return AdapterRunRequest.model_validate(payload)


def validate_run_response(payload: dict[str, Any]) -> AdapterRunResponse:
    response = AdapterRunResponse.model_validate(payload)
    if response.protocol_version != PROTOCOL_VERSION:
        raise ValueError(
            f"unsupported protocol_version: {response.protocol_version}"
        )
    return response


__all__ = [
    "PROTOCOL_VERSION",
    "AdapterManifest",
    "AdapterRunRequest",
    "AdapterRunResponse",
    "validate_run_request",
    "validate_run_response",
]
