from __future__ import annotations

from yai_scout.domain.models import Anchor, AnchorCandidate, BenchSession
from yai_scout.store import Store


def _store() -> Store:
    store = Store(":memory:")
    store.save_anchor(
        Anchor(
            id="a1",
            claim_key="k",
            url="https://example.com",
            status="active",
        )
    )
    return store


def test_clean_store_has_no_consistency_issues():
    store = _store()
    assert store.consistency_report() == []
    store.close()


def test_column_payload_mismatch_is_reported():
    store = _store()
    store._conn.execute("UPDATE anchor SET status = 'superseded' WHERE id = 'a1'")
    store._conn.commit()
    issues = store.consistency_report()
    assert any(
        item["table"] == "anchor"
        and item["id"] == "a1"
        and item["field"] == "status"
        for item in issues
    )
    store.close()


def test_orphan_candidate_is_reported():
    store = _store()
    candidate = AnchorCandidate(
        id="c1",
        anchor_id="missing_anchor",
        claim_key="k",
    )
    store._conn.execute(
        """INSERT INTO anchor_candidate
           (id, anchor_id, status, payload_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            candidate.id,
            candidate.anchor_id,
            candidate.accuracy_status,
            candidate.model_dump_json(),
            "2026-11-01",
        ),
    )
    store._conn.commit()
    issues = store.consistency_report()
    assert any(
        item["table"] == "anchor_candidate"
        and item["field"] == "orphan_anchor_id"
        for item in issues
    )
    store.close()

def test_bench_status_update_keeps_config_json_consistent():
    store = Store(":memory:")
    store.create_bench_session(BenchSession(id="b1", status="running"))
    store.update_bench_session("b1", status="done", finished_at="2026-11-02T00:00:00Z")
    assert store.consistency_report() == []
    store.close()
