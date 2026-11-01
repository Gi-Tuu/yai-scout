"""启动时把打包的 snapshots.json 灌入本地库（幂等），让无状态部署也能 replay。

用途：Render/HF 的容器没有持久盘；把真实快照随镜像分发，启动时落盘 + 入库，
replay 就不再依赖"部署后手工抓取"。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import EvidenceSnapshot
from ..store import Store


def seed_snapshots(store: Store, seed_path: Path, snapshots_dir: Path) -> int:
    if not seed_path.is_file():
        return 0
    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in payload.get("snapshots", []):
        try:
            text = str(item.pop("text", ""))
            snapshot = EvidenceSnapshot.model_validate(item)
        except (TypeError, ValueError):
            continue
        target = snapshots_dir / f"{snapshot.id}.txt"
        if not target.exists():
            target.write_text(text, encoding="utf-8")
        snapshot.text_path = str(target)
        store.save_snapshot(snapshot)
        count += 1
    return count
