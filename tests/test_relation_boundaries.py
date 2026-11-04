from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELATION = ROOT / "src" / "yai_scout" / "detector" / "relation"


def test_relation_package_does_not_import_verify_store_or_api() -> None:
    forbidden = {"verify", "store", "api"}
    for path in RELATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets: set[str] = set()
            if isinstance(node, ast.ImportFrom):
                if node.level >= 3 and node.module:
                    targets.add(node.module.split(".", 1)[0])
                elif node.level == 0 and node.module and node.module.startswith("yai_scout."):
                    targets.add(node.module.split(".", 1)[1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("yai_scout."):
                        targets.add(alias.name.split(".", 1)[1])
            assert not (targets & forbidden), f"{path.name} imports {targets}"
