"""Benchmark 数据集加载（支持 v0.1 四类 schema）。"""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import BenchmarkTask


def dataset_path() -> Path:
    # src/yai_scout/benchmark/dataset.py -> repo root
    return Path(__file__).resolve().parents[3] / "benchmarks" / "tasks.json"


def load_dataset(path: Path | None = None) -> tuple[str, list[BenchmarkTask]]:
    target = path or dataset_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "unknown")
    default_as_of = str(payload.get("as_of") or "2026-11-01")
    tasks: list[BenchmarkTask] = []
    for item in payload.get("tasks", []):
        merged = {"as_of": item.get("target_time") or default_as_of, **item}
        merged.pop("target_time", None)
        tasks.append(BenchmarkTask.model_validate(merged))
    return version, tasks


def load_tasks(path: Path | None = None) -> list[BenchmarkTask]:
    """公开数据集：永远不返回 hidden 题目。"""
    _, tasks = load_dataset(path)
    return [task for task in tasks if not task.hidden]


def load_private_dataset(path: Path) -> list[BenchmarkTask]:
    """私有评测集：必须显式给出仓库外的路径，仅受控环境调用。"""
    if not path.is_file():
        raise ValueError(f"private dataset not found: {path}")
    _, tasks = load_dataset(path)
    return tasks


