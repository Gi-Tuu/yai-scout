from __future__ import annotations

from pathlib import Path

from yai_scout.claim_classification import resolve_claim_type
from yai_scout.claim_keys import claim_key, claim_key_v2
from yai_scout.detector.candidates import apply_candidate
from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.domain.models import (
    Anchor,
    AnchorCandidate,
    CandidateEvidence,
    ClaimType,
)
from yai_scout.store import Store


class EmptySearcher:
    async def search(self, *args: object, **kwargs: object):
        return [], 0.0


def _anchor(anchor_id: str, text: str, *, version: int = 2) -> Anchor:
    resolved = resolve_claim_type(text)
    return Anchor(
        id=anchor_id,
        claim_key=claim_key(text),
        claim_key_v2=claim_key_v2(text, resolved),
        claim_key_version=version,
        claim_type=resolved,
        claim_text=text,
        url=f"https://example.com/{anchor_id}",
        last_value="0.24.0",
    )


def test_anchor_round_trip_keeps_type_and_v2_key():
    store = Store(":memory:")
    text = "YAI Agent Core 0.25.0"
    resolved = resolve_claim_type(text)
    anchor = _anchor("a1", text)
    store.save_anchor(anchor)
    loaded = store.get_anchor("a1")
    assert loaded is not None
    assert loaded.claim_type is resolved
    assert loaded.claim_key_v2 == claim_key_v2(text, resolved)
    assert store.consistency_report() == []
    store.close()


def test_migration_8_backfills_legacy_anchor(tmp_path: Path):
    path = tmp_path / "legacy.sqlite3"
    store = Store(path)
    text = "YAI Agent Core 0.25.0"
    legacy = Anchor(
        id="legacy",
        claim_key=claim_key(text),
        claim_key_v2="",
        claim_key_version=1,
        claim_type=ClaimType.OTHER,
        claim_text=text,
        url="https://example.com/legacy",
    )
    store.save_anchor(legacy)
    store._conn.execute(
        "UPDATE anchor SET claim_key_v2 = '', claim_key_version = 1, payload_json = ? "
        "WHERE id = 'legacy'",
        (legacy.model_dump_json(),),
    )
    store._conn.execute("DELETE FROM schema_version WHERE version = 8")
    store._conn.commit()
    store.close()

    reopened = Store(path)
    loaded = reopened.get_anchor("legacy")
    assert loaded is not None
    assert loaded.claim_type is ClaimType.VERSION
    assert loaded.claim_key_version == 2
    assert loaded.claim_key_v2 == claim_key_v2(text, ClaimType.VERSION)
    assert reopened.consistency_report() == []
    reopened.close()


async def test_detector_recalls_anchor_with_same_typed_identity():
    detector = StaleAnswerDetector(EmptySearcher(), as_of="2026-11-01")
    anchor = _anchor("a1", "YAI Agent Core 0.24.0")
    report = await detector.detect("YAI Agent Core 0.25.0.", anchors=[anchor])
    assert report.verdicts[0].anchor_id == "a1"


async def test_detector_does_not_merge_version_specific_facts():
    detector = StaleAnswerDetector(EmptySearcher(), as_of="2026-11-01")
    anchor = _anchor("py312", "Python 3.12 is supported")
    report = await detector.detect("Python 3.13 is supported.", anchors=[anchor])
    assert report.verdicts[0].anchor_id is None


def test_candidate_apply_and_rollback_preserve_identity():
    store = Store(":memory:")
    text = "Tavily free plan provides 500 credits"
    old = _anchor("old", text)
    old = old.model_copy(update={"last_value": "500"})
    store.save_anchor(old)
    candidate = AnchorCandidate(
        id="c1",
        anchor_id="old",
        claim_key=old.claim_key,
        claim_key_v2=old.claim_key_v2,
        claim_key_version=old.claim_key_version,
        claim_type=old.claim_type,
        old_value="500",
        new_value="1000",
        normalized_old="500",
        normalized_new="1000",
        evidence=[
            CandidateEvidence(
                url="https://docs.example.com/credits",
                source_tier=1,
                value="1000",
            )
        ],
        gate_decision="auto_update",
    )
    store.save_anchor_candidate(candidate)
    updated = apply_candidate(store, candidate, status="approved", decided_by="test")
    assert updated.applied_anchor_id
    new_anchor = store.get_anchor(updated.applied_anchor_id)
    assert new_anchor is not None
    assert new_anchor.claim_type is old.claim_type
    assert new_anchor.claim_key == old.claim_key
    assert new_anchor.claim_key_v2 == old.claim_key_v2

    rolled = store.rollback_anchor(new_anchor.id)
    assert rolled is not None
    restored, rolled_back = rolled
    assert restored.id == "old"
    assert restored.status == "active"
    assert rolled_back.status == "rolled_back"
    store.close()
