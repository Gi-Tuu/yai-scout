from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.detector.revalidate import due_anchors, revalidate_due
from yai_scout.domain.models import Anchor, TemporalSensitivity
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
    candidates = store.list_anchor_candidates()
    assert len(candidates) == 1
    assert candidates[0].accuracy_status == "pending"
    assert candidates[0].gate_decision == "review"
    assert candidates[0].new_value == "1000"
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


