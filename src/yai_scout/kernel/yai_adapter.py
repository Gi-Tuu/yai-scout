"""YAI Agent Core 唯一依赖面。

业务代码只允许 import 这里；YAI 升级时只改本文件 + 跑契约测试。
当前 G0 只验证内核可用性与版本，不参与检索流水线（检索不需要 LLM）。
"""

from __future__ import annotations

from typing import Any

KERNEL_REQUIRED_VERSION = "0.25.0"


def kernel_status() -> dict[str, Any]:
    """返回内核版本与关键符号是否可用（不创建实例，不联网）。"""
    import yai_core

    exported = {
        "AgentCore": hasattr(yai_core, "AgentCore"),
        "ModelProvider": _has_model_provider(),
        "ToolSpec": hasattr(yai_core, "ToolSpec"),
        "Budget": hasattr(yai_core, "Budget"),
        "EventType": hasattr(yai_core, "EventType"),
    }
    version = getattr(yai_core, "__version__", "unknown")
    return {
        "version": version,
        "expected": KERNEL_REQUIRED_VERSION,
        "match": version == KERNEL_REQUIRED_VERSION,
        "symbols": exported,
    }


def _has_model_provider() -> bool:
    """ModelProvider 不在顶层 __all__，但在 yai_core.spi 契约里。"""
    try:
        from yai_core.spi import ModelProvider  # noqa: F401
    except ImportError:
        return False
    return True


def build_agent_core(model: Any, tools: list[Any] | None = None) -> Any:
    """构造一个 YAI AgentCore（供后续检索 worker / 核查 worker 使用）。

    model 需实现 YAI 的 ModelProvider SPI；tools 为 ToolSpec 列表。
    """
    from yai_core import AgentCore

    core = AgentCore(model)
    if tools:
        core.register_tools(tools)
    return core
