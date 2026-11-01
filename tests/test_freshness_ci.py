import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freshness_ci", ROOT / "scripts" / "freshness_ci.py")
assert spec and spec.loader
freshness_ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freshness_ci)


def test_decide_filters_configured_statuses():
    verdicts = [
        {"claim_id": "a", "status": "fresh"},
        {"claim_id": "b", "status": "stale"},
        {"claim_id": "c", "status": "conflicted"},
        {"claim_id": "d", "status": "insufficient"},
    ]
    failing = freshness_ci.decide(verdicts, {"stale", "conflicted"})
    assert [item["claim_id"] for item in failing] == ["b", "c"]


def test_decide_can_fail_on_insufficient():
    failing = freshness_ci.decide(
        [{"claim_id": "a", "status": "insufficient"}], {"insufficient"}
    )
    assert len(failing) == 1
