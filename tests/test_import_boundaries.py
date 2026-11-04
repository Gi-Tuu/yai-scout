from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "src" / "yai_scout" / "storage"


def test_storage_does_not_import_store_or_upper_layers() -> None:
    forbidden = {
        "api", "benchmark", "detector", "pipeline", "retrieval", "sources", "store",
    }
    for path in STORAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            target = ""
            if isinstance(node, ast.ImportFrom):
                if node.level == 2 and node.module:
                    target = node.module.split(".", 1)[0]
                elif node.level == 0 and node.module and node.module.startswith("yai_scout."):
                    target = node.module.split(".", 1)[1]
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("yai_scout."):
                        target = alias.name.split(".", 1)[1]
            assert target not in forbidden, f"{path.name} imports {target}"
