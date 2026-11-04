"""Static page security regressions: no inline scripts/event handlers under CSP."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "static"


def test_static_html_has_no_inline_script_or_event_handlers() -> None:
    for page in sorted(STATIC.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        assert "<script>" not in text, page.name
        assert not re.search(r"\son[a-z]+\s*=", text, re.I), page.name
        assert "javascript:" not in text.lower(), page.name


def test_external_script_references_exist() -> None:
    for page in sorted(STATIC.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for match in re.finditer(r'<script\s+src="([^"]+)"', text):
            path = match.group(1)
            assert path.startswith("/static/")
            target = STATIC / path.removeprefix("/static/")
            assert target.is_file(), f"{page.name} references missing {path}"


def test_static_js_has_no_generated_inline_handlers() -> None:
    for script in sorted((STATIC / "js").glob("*.js")):
        text = script.read_text(encoding="utf-8")
        assert not re.search(r"on(?:click|change|input|submit|load)=", text, re.I), script.name
