from pathlib import Path

from yai_scout.sources.seed import seed_snapshots
from yai_scout.store import Store


def _seed_file(tmp_path: Path) -> Path:
    payload = {
        "version": "snapshots/0.1",
        "snapshots": [
            {
                "id": "snap_test1",
                "url": "https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.25.0",
                "title": "v0.25.0",
                "origin": "official_history",
                "content_hash": "abc",
                "published_at": "2026-10-31T00:00:00Z",
                "updated_at": None,
                "fetched_at": "2026-11-01T00:00:00Z",
                "tier": 2,
                "notes": "test",
                "text": "release version v0.25.0\npublished_at 2026-10-31T00:00:00Z",
            }
        ],
    }
    import json

    path = tmp_path / "snapshots.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_seed_snapshots_is_idempotent(tmp_path: Path):
    store = Store(":memory:")
    seed_file = _seed_file(tmp_path)
    target = tmp_path / "snapshots"
    assert seed_snapshots(store, seed_file, target) == 1
    assert seed_snapshots(store, seed_file, target) == 1
    snapshots = store.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].id == "snap_test1"
    assert Path(snapshots[0].text_path).is_file()
    store.close()
