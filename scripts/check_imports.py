"""Enforce a simple dependency direction for the package (CI guard)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "yai_scout"
LAYERS = {
    "api", "benchmark", "detector", "domain", "pipeline", "retrieval",
    "sources", "storage", "store",
}
RULES: dict[str, set[str]] = {
    "domain": set(),
    "storage": {"domain"},
    "store": {"domain", "storage"},
    "retrieval": {"domain"},
    "sources": {"domain", "retrieval", "store"},
    "detector": {"domain", "retrieval", "sources", "store", "llm"},
    "pipeline": {"domain", "retrieval", "sources", "store", "llm"},
    "benchmark": {"domain", "retrieval", "detector", "pipeline", "store", "llm"},
    "api": LAYERS,
}


def _layer(path: Path) -> str | None:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return None
    return relative.parts[0].removesuffix(".py") if relative.parts else None


def _targets(tree: ast.AST, current: str) -> set[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level == 1:
                    targets.add(current)
                elif node.module:
                    targets.add(node.module.split(".", 1)[0])
            elif node.module and node.module.startswith("yai_scout."):
                targets.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("yai_scout."):
                    targets.add(alias.name.split(".")[1])
    return targets


def main() -> int:
    failures: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        layer = _layer(path)
        if layer not in RULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for target in _targets(tree, layer):
            if target in LAYERS and target not in RULES[layer] and target != layer:
                failures.append(f"{path.relative_to(ROOT.parent.parent)}: {layer} -> {target}")
    if failures:
        print("architecture violations:")
        for item in failures:
            print(" ", item)
        return 1
    print("architecture: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

