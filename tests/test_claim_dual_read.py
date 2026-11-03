from __future__ import annotations

from yai_scout.claim_keys import claim_key, claim_key_v2
from yai_scout.detector.service import StaleAnswerDetector
from yai_scout.domain.models import Anchor


class EmptySearcher:
    async def search(self, *args: object, **kwargs: object):
        return [], 0.0


def _anchor(anchor_id: str, text: str, *, version: int = 2) -> Anchor:
    return Anchor(
        id=anchor_id,
        claim_key=claim_key(text),
        claim_key_v2=claim_key_v2(text, "statistic"),
        claim_key_version=version,
        claim_text=text,
        url=f"https://example.com/{anchor_id}",
        last_value="600",
    )


async def test_detector_prefers_v2_and_does_not_merge_quarters():
    detector = StaleAnswerDetector(EmptySearcher(), as_of="2026-11-01")
    anchors = [
        _anchor("q1", "Q1 revenue increased 600 percent"),
        _anchor("q2", "Q2 revenue increased 600 percent"),
    ]
    report = await detector.detect("Q2 revenue increased 600 percent.", anchors=anchors)
    assert report.verdicts[0].anchor_id == "q2"


async def test_detector_falls_back_to_legacy_v1_anchor():
    detector = StaleAnswerDetector(EmptySearcher(), as_of="2026-11-01")
    text = "Q2 revenue increased 600 percent"
    legacy = Anchor(
        id="legacy",
        claim_key=claim_key(text),
        claim_key_version=1,
        claim_text=text,
        url="https://example.com/legacy",
        last_value="600",
    )
    report = await detector.detect(text + ".", anchors=[legacy])
    assert report.verdicts[0].anchor_id == "legacy"

