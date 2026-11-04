"""集中配置：环境变量 / .env → Settings；预算与路径默认值都在这里。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/yai_scout/config.py -> 项目根
ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """运行配置。所有字段可用同名大写环境变量覆盖（如 TAVILY_API_KEY）。"""

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "YAI Scout"
    app_version: str = "0.5.2"
    # all | benchmark | freshness —— 用于独立部署/独立入口
    scout_mode: str = "all"
    snapshots_seed: str = "benchmarks/snapshots.json"
    admin_token: str = ""
    # Optional one-off diagnostic token for XFF/proxy header inspection.
    # Empty disables the diagnostic endpoint.
    xff_debug_token: str = ""
    benchmark_run_requires_admin: bool = True
    benchmark_public_agent_ids: str = "mock_good,mock_stale"
    accuracy_auto_update: bool = False
    anchor_live_fetch: bool = False
    anchor_allowlist: str = ""
    anchor_discovery_ttl_seconds: int = 3600
    anchor_discovery_daily_budget: int = 50
    anchor_discovery_cache_entries: int = 256
    # 可选：公开创建 Anchor 的 host 白名单（逗号分隔）；空 = 不限制 host。
    anchor_create_allowlist: str = ""

    # --- 公开 Demo 成本保护（单进程内存计数，重启清零）---
    demo_limits_enabled: bool = True
    rate_limit_per_minute: int = 4
    daily_detector_limit: int = 60
    daily_benchmark_limit: int = 20
    # 0 disables automatic benchmark retention; explicit opt-in only.
    benchmark_retention_days: int = Field(default=0, ge=0)
    daily_anchor_limit: int = 30
    daily_research_limit: int = 5
    max_active_research_tasks: int = 2
    research_enabled: bool = True
    # 公开 Demo 默认禁止匿名创建全局 Anchor；需要时显式打开或使用 ADMIN_TOKEN。
    public_anchor_writes: bool = False
    # 可选：外部 Agent（scout-adapter/1.0）的 base URL
    http_agent_url: str = ""

    # --- Tavily ---
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    # 没有 key 时允许退回 keyless（Search/Extract 免鉴权，有限速）；仅用于开发/应急。
    tavily_allow_keyless: bool = True
    tavily_timeout_seconds: float = 30.0
    search_depth: str = "basic"
    max_results_per_query: int = 5

    # --- 研究流水线预算（G0 只有检索阶段吃预算）---
    max_queries: int = Field(default=4, ge=1, le=8)
    max_concurrency: int = Field(default=3, ge=1, le=8)
    max_tavily_credits: int = Field(default=32, ge=1)
    max_wall_clock_seconds: int = Field(default=360, ge=30)

    # --- 存储与默认值 ---
    db_path: Path = ROOT / "data" / "scout.sqlite3"
    web_dir: Path = ROOT / "web"
    default_as_of: str = "2026-11-01"

    # --- 模型（G0 未启用，留好接口）---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    # Bifrost AI Gateway：设置后所有模型请求走 Bifrost 的 OpenAI-compatible endpoint。
    bifrost_base_url: str = ""
    bifrost_api_key: str = ""
    bifrost_model: str = ""
    full_page_fetch_enabled: bool = False
    full_page_allowlist: str = ""

    def benchmark_public_agents(self) -> set[str]:
        return {
            item.strip()
            for item in self.benchmark_public_agent_ids.split(",")
            if item.strip()
        }

    def full_page_hosts(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.full_page_allowlist.split(",")
            if item.strip()
        }

    def llm_connection(self) -> dict[str, str | bool]:
        """Single source of truth for the effective LLM endpoint."""
        if self.bifrost_base_url:
            return {
                "base_url": self.bifrost_base_url.rstrip("/"),
                "api_key": self.bifrost_api_key,
                "model": self.bifrost_model or self.llm_model,
                "gateway": "bifrost",
                "require_key": False,
            }
        return {
            "base_url": self.openai_base_url.rstrip("/"),
            "api_key": self.openai_api_key,
            "model": self.llm_model,
            "gateway": "direct",
            "require_key": True,
        }


def get_settings() -> Settings:
    """返回配置（测试可替换）。"""
    return Settings()















