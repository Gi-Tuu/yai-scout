from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _values() -> dict[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)["project"]["version"]
    init = re.search(
        r'__version__\s*=\s*"([^"]+)"',
        (ROOT / "src/yai_scout/__init__.py").read_text(encoding="utf-8"),
    )
    config = re.search(
        r'app_version\s*:\s*str\s*=\s*"([^"]+)"',
        (ROOT / "src/yai_scout/config.py").read_text(encoding="utf-8"),
    )
    changelog = re.search(
        r"^## \[(\d+\.\d+\.\d+)\]",
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert init and config and changelog
    return {
        "pyproject": pyproject,
        "init": init.group(1),
        "config": config.group(1),
        "changelog": changelog.group(1),
    }


def test_version_sources_match() -> None:
    values = _values()
    assert len(set(values.values())) == 1, values
    assert re.fullmatch(r"\d+\.\d+\.\d+", values["pyproject"])
