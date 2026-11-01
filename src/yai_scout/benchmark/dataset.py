"""Benchmark 数据集加载。"""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import BenchmarkTask


def dataset_path() -> Path:
    # src/yai_scout/benchmark/dataset.py -> repo root
    return Path(__file__).resolve().parents[3] / "benchmarks" / "tasks.json"


def load_tasks(path: Path | None = None) -> list[BenchmarkTask]:
    target = path or dataset_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    default_as_of = str(payload.get("as_of") or "2026-11-01")
    tasks: list[BenchmarkTask] = []
    for item in payload.get("tasks", []):
        merged = {"as_of": default_as_of, **item}
        tasks.append(BenchmarkTask.model_validate(merged))
    return tasks
