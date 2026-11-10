#!/usr/bin/env python3
"""Run the repository's configured quality gates in one command."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, *args: str) -> None:
    print(f"\n== {label} ==")
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{label} failed (exit {result.returncode})")


def main() -> int:
    run("tests", "-m", "pytest", "-q")
    run("ruff", "-m", "ruff", "check", "src", "tests", "scripts", "examples")
    run("mypy", "-m", "mypy")
    run("version", "scripts/check_version.py")
    run("imports", "scripts/check_imports.py")
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
