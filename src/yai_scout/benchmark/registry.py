"""Agent 注册表：把 AgentSpec 变成可运行的适配器。"""

from __future__ import annotations

from ..domain.models import AgentSpec
from ..llm import LLMClient
from ..retrieval.tavily import TavilyClient
from .adapters import (
    AgentAdapter,
    CLIAdapter,
    HttpAdapter,
    LLMAgentAdapter,
    MockAdapter,
    PythonAdapter,
    RetrievalAdapter,
    ScoutAdapter,
)
from .runner import DEFAULT_AGENT_SPECS


def build_adapters(tavily: TavilyClient, llm: LLMClient | None = None) -> dict[str, AgentAdapter]:
    adapters: dict[str, AgentAdapter] = {
        "mock_good": MockAdapter("mock_good", "Mock (fresh)", good=True),
        "mock_stale": MockAdapter("mock_stale", "Mock (stale)", good=False),
        "retrieval_baseline": RetrievalAdapter(tavily),
        "scout": ScoutAdapter(tavily),
    }
    if llm is not None and llm.available:
        adapters["llm_agent"] = LLMAgentAdapter(tavily, llm)
    return adapters


def adapter_from_spec(
    spec: AgentSpec, tavily: TavilyClient, llm: LLMClient | None = None
) -> AgentAdapter:
    if spec.kind == "mock":
        return MockAdapter(spec.id, spec.name, good=bool(spec.config.get("good", True)))
    if spec.kind == "retrieval_baseline":
        return RetrievalAdapter(tavily)
    if spec.kind == "scout":
        return ScoutAdapter(tavily)
    if spec.kind == "llm":
        if llm is None or not llm.available:
            raise ValueError("llm adapter requires a configured LLM key")
        return LLMAgentAdapter(tavily, llm)
    if spec.kind == "http":
        endpoint = str(spec.config.get("endpoint") or "")
        if not endpoint:
            raise ValueError("http adapter requires config.endpoint")
        return HttpAdapter(spec.id, spec.name, endpoint)
    if spec.kind == "python":
        target = str(spec.config.get("target") or "")
        if not target:
            raise ValueError("python adapter requires config.target")
        return PythonAdapter(spec.id, spec.name, target)
    if spec.kind == "cli":
        command = spec.config.get("command")
        if not isinstance(command, list) or not command:
            raise ValueError("cli adapter requires config.command")
        return CLIAdapter(spec.id, spec.name, [str(part) for part in command])
    raise ValueError(f"unknown agent kind: {spec.kind}")


__all__ = ["DEFAULT_AGENT_SPECS", "adapter_from_spec", "build_adapters"]

