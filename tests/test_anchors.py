from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.detector.compare import claim_key
from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.domain.models import Anchor
from yai_scout.sources.anchor import replay_anchor_result
from yai_scout.sources.snapshot import save_snapshot
from yai_scout.store import Store


class FakeTavily:
    mode = "fake"
    authenticated = False

    async def search(self, *args: object, **kwargs: object):
        return [], 0.0

    async def aclose(self) -> None:
        return None


def _anchor(store: Store, tmp_path: Path) -> Anchor:
    snapshot = save_snapshot(
        store,
        url="https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0",
        text="release version v0.24.0\npublished_at 2026-10-27T08:11:51Z",
        origin="official_history",
        snapshots_dir=tmp_path,
        published_at="2026-10-27T08:11:51Z",
    )
    anchor = Anchor(
        id="anc_test",
        claim_key=claim_key("YAI Agent Core 当前版本是 0.24.0"),
        claim_text="YAI Agent Core 当前版本是 0.24.0",
        url=snapshot.url,
        source_tier=2,
        last_value="0.24.0",
        published_at=snapshot.published_at,
    )
    store.save_anchor(anchor)
    return anchor


async def test_replay_uses_anchor_snapshot(tmp_path: Path):
    store = Store(":memory:")
    anchor = _anchor(store, tmp_path)

    async def fetcher(item: Anchor, target: str):
        return await replay_anchor_result(store, item, target)

    detector = StaleAnswerDetector(
        FakeTavily(),
        as_of="2026-10-28",
        max_claims=1,
        mode="replay",
        anchor_fetcher=fetcher,
    )
    report = await detector.detect(
        "YAI Agent Core 当前版本是 0.24.0。", anchors=store.list_anchors()
    )
    verdict = report.verdicts[0]
    assert verdict.anchor_id == anchor.id
    assert verdict.anchor_status == "used"
    assert verdict.status.value == "fresh"
    store.close()


async def test_without_anchor_keeps_behavior(tmp_path: Path):
    store = Store(":memory:")
    _anchor(store, tmp_path)
    detector = StaleAnswerDetector(FakeTavily(), as_of="2026-10-28", max_claims=1)
    report = await detector.detect(
        "YAI Agent Core 当前版本是 0.24.0。", anchors=[]
    )
    assert report.verdicts[0].anchor_id is None
    store.close()


def test_anchor_api_create_and_list():
    settings = Settings(
        _env_file=None,
        db_path=":memory:",
        openai_api_key="",
        tavily_api_key="",
        demo_limits_enabled=False,
    )
    app = create_app(
        settings=settings, tavily=FakeTavily(), store=Store(":memory:")  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        created = client.post(
            "/freshness/anchors",
            json={
                "claim_text": "Tavily 免费计划每月提供 1,000 credits",
                "url": "https://docs.tavily.com/documentation/api-credits",
                "last_value": "1000",
                "source_tier": 1,
            },
        )
        assert created.status_code == 201
        anchor_id = created.json()["id"]
        listed = client.get("/freshness/anchors").json()["anchors"]
        assert [item["id"] for item in listed] == [anchor_id]
