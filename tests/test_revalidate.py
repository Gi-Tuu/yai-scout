from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.detector.candidates import (
    create_candidate_from_observations,
    independent_group_from_url,
)
from yai_scout.detector.revalidate import due_anchors, revalidate_due
from yai_scout.domain.models import Anchor, AnchorObservation, TemporalSensitivity
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.sources.snapshot import save_snapshot
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def _store_with_anchor(tmp_path: Path) -> Store:
    store = Store(":memory:")
    snapshot = save_snapshot(
        store,
        url="https://example.com/pricing",
        text="current price 1000",
        origin="live",
        snapshots_dir=tmp_path,
        published_at="2026-01-01T00:00:00Z",
    )
    anchor = Anchor(
        id="anc_old",
        claim_key="price #",
        url=snapshot.url,
        source_tier=1,
        last_value="500",
        content_hash="old-hash",
        published_at=snapshot.published_at,
        last_verified_at="2025-01-01T00:00:00Z",
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )
    store.save_anchor(anchor)
    return store


def test_due_anchors_uses_sensitivity_ttl(tmp_path: Path):
    store = _store_with_anchor(tmp_path)
    due = due_anchors(store, now=datetime(2026, 11, 1, tzinfo=UTC))
    assert [anchor.id for anchor in due] == ["anc_old"]
    store.close()


async def test_revalidate_records_change_without_overwriting(tmp_path: Path):
    store = _store_with_anchor(tmp_path)
    observations = await revalidate_due(
        store, now=datetime(2026, 11, 1, tzinfo=UTC)
    )
    assert observations[0].status == "changed"
    assert observations[0].content_changed is True
    anchor = store.list_anchors()[0]
    assert anchor.last_value == "500"
    assert store.list_anchor_observations()[0].status == "changed"
    assert store.list_anchor_observations()[0].independent_group == "example.com"
    candidates = store.list_anchor_candidates()
    assert len(candidates) == 1
    assert candidates[0].accuracy_status == "pending"
    assert candidates[0].gate_decision == "review"
    assert candidates[0].new_value == "1000"
    assert due_anchors(store, now=datetime(2026, 11, 1, tzinfo=UTC)) == []
    store.close()


def test_admin_endpoint_requires_token(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
        admin_token="secret-token",
    )
    store = _store_with_anchor(tmp_path)
    app = create_app(settings=settings, tavily=FakeTavily(), store=store)  # type: ignore[arg-type]
    with TestClient(app) as client:
        assert client.post("/admin/anchors/revalidate").status_code == 401
        response = client.post(
            "/admin/anchors/revalidate",
            headers={"Authorization": "Bearer secret-token"},
        )
        assert response.status_code == 200
        assert response.json()["checked"] == 1
    store.close()



async def test_revalidation_discovers_independent_sources(tmp_path: Path):
    store = _store_with_anchor(tmp_path)

    class Discovery:
        async def search(self, *args: object, **kwargs: object):
            return [
                SearchResult(
                    title="docs",
                    url="https://docs.example.com/pricing",
                    content="current price 1000 credits",
                    published_date="2026-10-01T00:00:00Z",
                    content_hash="h1",
                ),
                SearchResult(
                    title="github",
                    url="https://github.com/org/repo",
                    content="current price 1000 credits",
                    published_date="2026-10-02T00:00:00Z",
                    content_hash="h2",
                ),
            ], 0.0

    await revalidate_due(
        store,
        discovery=Discovery(),  # type: ignore[arg-type]
        now=datetime(2026, 11, 1, tzinfo=UTC),
    )
    candidates = store.list_anchor_candidates()
    assert candidates
    assert candidates[0].gate_decision == "auto_update"
    assert candidates[0].accuracy_status == "pending"
    assert len(candidates[0].evidence) >= 2
    store.close()

def test_candidate_reject_status_and_dedupe(tmp_path: Path):
    store = _store_with_anchor(tmp_path)
    anchor = store.list_anchors()[0]
    observation = AnchorObservation(
        id="obs_reject",
        anchor_id=anchor.id,
        status="changed",
        content_changed=True,
        observed_hash="h",
        url="https://some-blog.example/post",
        source_tier=3,
        independent_group="some-blog.example",
        value="1200",
        published_at="2026-10-01T00:00:00Z",
    )
    first = create_candidate_from_observations(store, anchor, [observation])
    second = create_candidate_from_observations(store, anchor, [observation])
    assert first is not None and second is not None
    assert first.id == second.id
    assert first.gate_decision == "reject"
    assert first.accuracy_status == "rejected"
    assert len(store.list_anchor_candidates()) == 1
    store.close()


def test_independent_group_uses_registrable_domain():
    assert independent_group_from_url("https://docs.tavily.com/x") == "tavily.com"
    assert independent_group_from_url("https://github.com/a/b") == "github.com"

