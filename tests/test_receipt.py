from __future__ import annotations

from fastapi.testclient import TestClient

from yai_scout.api.app import create_app
from yai_scout.config import Settings
from yai_scout.detector.receipt import RECEIPT_VERSION, build_report_receipt
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    DetectorReport,
    EvidenceKind,
    EvidenceRef,
    FreshnessStatus,
    FreshnessVerdict,
)
from yai_scout.store import Store


def _report() -> DetectorReport:
    claim = Claim(
        id="c1",
        text="Tavily 免费计划每月提供 1000 credits",
        type=ClaimType.PRICING,
    )
    evidence = EvidenceRef(
        url="https://docs.tavily.com/x",
        title="Tavily docs",
        domain="docs.tavily.com",
        tier=1,
        snippet="1000 credits",
        evidence_kind=EvidenceKind.SEARCH_SNIPPET,
        fetch_status="snippet",
        content_hash="abc",
        relation="supports",
    )
    verdict = FreshnessVerdict(
        claim_id="c1",
        status=FreshnessStatus.FRESH,
        score=80,
        rationale="authoritative support",
        evidence=[evidence],
    )
    return DetectorReport(
        id="det_1",
        answer="a",
        as_of="2026-11-01",
        claims=[claim],
        verdicts=[verdict],
        overall_score=80,
        total_claims=1,
        scored_claims=1,
        coverage=1.0,
        policy_version="p",
        weights_version="w",
    )


def test_receipt_is_versioned_and_traceable():
    receipt = build_report_receipt(_report())
    assert receipt.receipt_version == RECEIPT_VERSION
    assert receipt.report_id == "det_1"
    assert receipt.claims[0].claim_text.startswith("Tavily")
    item = receipt.claims[0].evidence[0]
    assert item.content_hash == "abc"
    assert item.evidence_kind is EvidenceKind.SEARCH_SNIPPET
    assert any("not full-page" in line for line in receipt.limitations)
    assert any("AUTO_UPDATE remains disabled" in line for line in receipt.limitations)


def test_receipt_does_not_claim_source_authenticity():
    receipt = build_report_receipt(_report())
    assert any("not source authenticity" in line for line in receipt.limitations)


def test_receipt_endpoint_returns_versioned_json():
    store = Store(":memory:")
    store.save_detector_report(_report())
    app = create_app(
        settings=Settings(
            db_path=":memory:",
            demo_limits_enabled=False,
            admin_token="secret",
        ),
        store=store,
    )
    with TestClient(app) as client:
        response = client.get(
            "/freshness/reports/det_1/receipt",
            headers={"Authorization": "Bearer secret"},
        )
    store.close()
    assert response.status_code == 200
    assert response.json()["receipt_version"] == RECEIPT_VERSION
