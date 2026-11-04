from __future__ import annotations

import json
from pathlib import Path

from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.detector.snapshot_search import SnapshotSearcher
from yai_scout.sources.seed import seed_snapshots
from yai_scout.store import Store

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "demo" / "cases.json"
CACHE = ROOT / "benchmarks" / "demo" / "responses.json"


def _cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))["cases"]


async def test_fixed_replay_cases_offline(tmp_path: Path) -> None:
    store = Store(":memory:")
    seed_snapshots(
        store,
        ROOT / "benchmarks" / "snapshots.json",
        tmp_path / "snapshots",
    )
    for case in _cases():
        if case["mode"] != "replay":
            continue
        detector = StaleAnswerDetector(
            SnapshotSearcher(store, target_time=case["as_of"]),
            as_of=case["as_of"],
            max_claims=3,
            mode="replay",
        )
        report = await detector.detect(case["answer"])
        assert report.verdicts
        assert report.verdicts[0].status.value in {
            case["expected_status"],
        }, case["id"]
    store.close()


def test_fixed_cache_matches_expected_statuses() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    for case in _cases():
        report = cache[case["id"]]
        statuses = [verdict["status"] for verdict in report["verdicts"]]
        assert case["expected_status"] in statuses, (
            f"{case['id']} cache drift; run demo_fixed_cases.py --record"
        )
