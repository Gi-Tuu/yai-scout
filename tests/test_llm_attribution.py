from __future__ import annotations

from yai_scout.detector.verify import ClaimVerifier
from yai_scout.domain.models import Claim, ClaimType, EvidenceKind
from yai_scout.llm import LLMResult
from yai_scout.retrieval.tavily import SearchResult


class FakeSearcher:
    async def search(self, query: str, *, depth=None, max_results=None):
        return [
            SearchResult(
                title="source a",
                url="https://a.example/x",
                content="Bifrost license page",
            ),
            SearchResult(
                title="source b",
                url="https://b.example/x",
                content="Bifrost license page",
            ),
        ], 1.0


class FakeLLM:
    available = True

    async def chat_json(self, system: str, user: str, **kwargs):
        return (
            {"relation": "supports", "reason": "aggregate judgement"},
            LLMResult(text="{}", prompt_tokens=1, completion_tokens=1, cost_usd=0.001),
        )


async def test_llm_assessment_does_not_overwrite_evidence_relation():
    verifier = ClaimVerifier(
        FakeSearcher(),
        as_of="2026-11-01",
        llm=FakeLLM(),  # type: ignore[arg-type]
        use_llm_relations=True,
    )
    claim = Claim(
        id="c1",
        text="Bifrost 使用 MIT 许可证",
        type=ClaimType.LAW,
        numbers=[],
    )
    verdict, _, cost = await verifier.verify(claim)
    assert cost > 0
    assert verdict.claim_assessment is not None
    assert verdict.claim_assessment.relation == "supports"
    assert verdict.status.value == "insufficient"
    assert all(item.relation == "mentions" for item in verdict.evidence)
    assert all(
        item.evidence_kind is EvidenceKind.SEARCH_SNIPPET for item in verdict.evidence
    )
