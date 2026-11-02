from __future__ import annotations

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.domain.models import Anchor, TemporalSensitivity
from yai_scout.store import Store

AUTH = {"Authorization": "Bearer secret"}


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def _app(store: Store, *, auto: bool = False):
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
        admin_token="secret",
        accuracy_auto_update=auto,
    )
    return create_app(settings=settings, tavily=FakeTavily(), store=store)  # type: ignore[arg-type]


def _anchor(store: Store) -> Anchor:
    anchor = Anchor(
        id="anc_old",
        claim_key="tavily 免费计划每月提供 # credits",
        claim_text="Tavily 免费计划每月提供 500 credits",
        url="https://docs.tavily.com/documentation/api-credits",
        source_tier=1,
        last_value="500",
        published_at="2025-01-01T00:00:00Z",
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )
    store.save_anchor(anchor)
    return anchor


def _observations() -> list[dict[str, object]]:
    return [
        {
            "url": "https://docs.tavily.com/documentation/api-credits",
            "source_tier": 1,
            "independent_group": "tavily-docs",
            "value": "1000",
            "published_at": "2026-10-01T00:00:00Z",
            "content_hash": "new-a",
        },
        {
            "url": "https://github.com/tavily-ai/tavily-python",
            "source_tier": 2,
            "independent_group": "tavily-github",
            "value": "1,000",
            "published_at": "2026-10-02T00:00:00Z",
            "content_hash": "new-b",
        },
    ]


def test_candidate_requires_admin():
    store = Store(":memory:")
    anchor = _anchor(store)
    app = _app(store)
    with TestClient(app) as client:
        response = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={"observations": _observations()},
        )
        assert response.status_code == 401
    store.close()


def test_review_candidate_can_be_approved():
    store = Store(":memory:")
    anchor = _anchor(store)
    app = _app(store)
    with TestClient(app) as client:
        created = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={"observations": _observations()},
            headers=AUTH,
        )
        assert created.status_code == 201
        candidate = created.json()
        assert candidate["accuracy_status"] == "pending"
        assert candidate["gate_decision"] == "auto_update"

        approved = client.post(
            f"/admin/anchors/candidates/{candidate['id']}/approve",
            headers=AUTH,
        )
        assert approved.status_code == 200
        assert approved.json()["accuracy_status"] == "approved"

        old = store.get_anchor(anchor.id)
        assert old is not None and old.status == "superseded"
        active = store.list_anchors()
        assert len(active) == 1
        assert active[0].last_value in {"1000", "1,000"}
        assert active[0].supersedes == anchor.id
    store.close()


def test_review_candidate_can_be_rejected():
    store = Store(":memory:")
    anchor = _anchor(store)
    app = _app(store)
    with TestClient(app) as client:
        created = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={
                "observations": [
                    {
                        "url": "https://docs.tavily.com/documentation/api-credits",
                        "source_tier": 1,
                        "independent_group": "tavily-docs",
                        "value": "1000",
                        "published_at": "2026-10-01T00:00:00Z",
                    }
                ]
            },
            headers=AUTH,
        )
        candidate = created.json()
        assert candidate["gate_decision"] == "review"
        rejected = client.post(
            f"/admin/anchors/candidates/{candidate['id']}/reject",
            headers=AUTH,
        )
        assert rejected.status_code == 200
        assert rejected.json()["accuracy_status"] == "rejected"
    store.close()


def test_auto_update_flag_applies_immediately():
    store = Store(":memory:")
    anchor = _anchor(store)
    app = _app(store, auto=True)
    with TestClient(app) as client:
        created = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={"observations": _observations()},
            headers=AUTH,
        )
        assert created.status_code == 201
        assert created.json()["accuracy_status"] == "auto_applied"
        old = store.get_anchor(anchor.id)
        assert old is not None and old.status == "superseded"
        assert store.list_anchors()[0].last_value in {"1000", "1,000"}
    store.close()


def test_approved_candidate_can_be_rolled_back():
    store = Store(":memory:")
    anchor = _anchor(store)
    app = _app(store)
    with TestClient(app) as client:
        created = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={"observations": _observations()},
            headers=AUTH,
        )
        candidate = created.json()
        client.post(
            f"/admin/anchors/candidates/{candidate['id']}/approve", headers=AUTH
        )
        active = store.list_anchors()
        replacement = active[0]

        rolled = client.post(
            f"/admin/anchors/{replacement.id}/rollback", headers=AUTH
        )
        assert rolled.status_code == 200
        assert rolled.json()["restored"]["id"] == anchor.id
        assert rolled.json()["rolled_back_candidates"] == 1
        assert rolled.json()["audit_id"] > 0
        rolled_candidate = store.get_anchor_candidate(candidate["id"])
        assert rolled_candidate is not None
        assert rolled_candidate.accuracy_status == "rolled_back"
        assert store.get_anchor(anchor.id).status == "active"  # type: ignore[union-attr]
        assert store.get_anchor(replacement.id).status == "rolled_back"  # type: ignore[union-attr]
        assert [item.id for item in store.list_anchors()] == [anchor.id]
        audit = client.get("/admin/anchors/audit", headers=AUTH).json()["audit"]
        assert audit[0]["action"] == "rollback"
        assert audit[0]["anchor_id"] == replacement.id
    store.close()


def test_admin_page_is_served():
    store = Store(":memory:")
    app = _app(store)
    with TestClient(app) as client:
        assert client.get("/admin").status_code == 200
        assert client.get("/label").status_code == 200
    store.close()


def test_duplicate_candidate_api_is_deduped():
    store = Store(":memory:")
    anchor = _anchor(store)
    app = _app(store)
    with TestClient(app) as client:
        first = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={"observations": _observations()},
            headers=AUTH,
        ).json()
        second = client.post(
            f"/admin/anchors/{anchor.id}/candidates",
            json={"observations": _observations()},
            headers=AUTH,
        ).json()
        assert first["id"] == second["id"]
        assert len(store.list_anchor_candidates()) == 1
    store.close()
