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
    app_version: str = "0.1.0"

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


def get_settings() -> Settings:
    """返回配置（测试可替换）。"""
    return Settings()
