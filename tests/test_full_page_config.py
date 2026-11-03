from __future__ import annotations

from yai_scout.config import Settings


def test_full_page_allowlist_is_normalized():
    settings = Settings(
        _env_file=None,
        full_page_fetch_enabled=True,
        full_page_allowlist=" Docs.Tavily.com, api-docs.deepseek.com ,, ",
    )
    assert settings.full_page_hosts() == {
        "docs.tavily.com",
        "api-docs.deepseek.com",
    }


def test_full_page_is_disabled_by_default():
    settings = Settings(_env_file=None)
    assert settings.full_page_fetch_enabled is False
    assert settings.full_page_hosts() == set()
