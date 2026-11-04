#!/usr/bin/env python
"""Check that all declared YAI Scout versions agree with each other and optional tag."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_pyproject() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def _read_assign(path: str, pattern: str, label: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"{label}: version assignment not found")
    return match.group(1)


def _read_changelog() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    if not match:
        raise ValueError("CHANGELOG: no published version heading")
    return match.group(1)


def _check_tag(version: str) -> tuple[bool, str]:
    if not (ROOT / ".git").exists():
        return True, "no .git; tag check skipped"
    try:
        tag = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, f"unable to read git tag: {exc}"
    expected = f"v{version}"
    if tag != expected:
        return False, f"latest tag is {tag!r}, expected {expected!r}"
    return True, f"latest tag is {tag}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-tag",
        action="store_true",
        help="also compare the latest git tag with the declared version",
    )
    args = parser.parse_args(argv)

    values = {
        "pyproject.toml": _read_pyproject(),
        "__init__.py": _read_assign(
            "src/yai_scout/__init__.py", r'__version__\s*=\s*"([^"]+)"', "__init__.py"
        ),
        "config.py": _read_assign(
            "src/yai_scout/config.py",
            r'app_version\s*:\s*str\s*=\s*"([^"]+)"',
            "config.py",
        ),
        "CHANGELOG.md": _read_changelog(),
    }
    unique = set(values.values())
    for label, value in values.items():
        print(f"{label}: {value}")
    if len(unique) != 1:
        print("version mismatch", file=sys.stderr)
        return 1

    version = unique.pop()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(f"invalid semantic version: {version}", file=sys.stderr)
        return 1

    if args.check_tag:
        ok, message = _check_tag(version)
        print(message)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
