"""Freshness detector, report, anchor and admin routes."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..config import Settings
from ..detector.accuracy_gate import GateObservation, evaluate_gate
from ..detector.candidates import apply_candidate, independent_group_from_url
from ..detector.compare import claim_key, compare_reports
from ..detector.discovery import CachedDiscovery
from ..detector.receipt import build_report_receipt
from ..detector.revalidate import revalidate_due
from ..detector.service import StaleAnswerDetector
from ..detector.snapshot_search import SnapshotSearcher
from ..domain.models import (
    Anchor,
    AnchorCandidate,
    CandidateEvidence,
    TemporalSensitivity,
    utcnow_iso,
)
from ..llm import LLMClient
from ..retrieval.tavily import TavilyClient
from ..sources.anchor import live_anchor_result, replay_anchor_result
from ..store import Store


class DetectRequest(BaseModel):
    answer: str = Field(min_length=10, max_length=8000)
    as_of: str | None = None
    max_claims: int = Field(default=6, ge=1, le=12)
    mode: str = "live"
    use_anchors: bool = True


class AnchorCreate(BaseModel):
    claim_text: str = Field(min_length=3, max_length=800)
    url: str = Field(min_length=5, max_length=2000)
    last_value: str = ""
    content_hash: str = ""
    source_tier: int = Field(default=3, ge=1, le=4)
    published_at: str | None = None
    temporal_sensitivity: TemporalSensitivity | None = None


class RevalidateRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class ObservationInput(BaseModel):
    url: str
    source_tier: int = Field(default=3, ge=1, le=4)
    independent_group: str = ""
    value: str = ""
    published_at: str | None = None
    content_hash: str = ""
    reachable: bool = True


class CandidateCreate(BaseModel):
    observations: list[ObservationInput] = Field(default_factory=list)


def _require_admin(request: Request, cfg: Settings) -> None:
    if not cfg.admin_token:
        raise HTTPException(status_code=404, detail="admin endpoint disabled")
    if request.headers.get("authorization") != f"Bearer {cfg.admin_token}":
        raise HTTPException(status_code=401, detail="unauthorized")


def register_freshness_routes(
    app: FastAPI,
    *,
    cfg: Settings,
    store: Store,
    tavily: TavilyClient,
    llm: LLMClient,
    detector: StaleAnswerDetector,
    discovery: CachedDiscovery,
    guard_cost: Callable[[Request, str], None],
    session_id: Callable[..., str],
    can_access: Callable[[str, Request], bool],
    is_admin: Callable[[Request], bool],
    validated_as_of: Callable[[str | None], str],
) -> None:
    @app.post("/api/detector")
    @app.post("/freshness/verify")
    async def detect(
        payload: DetectRequest, request: Request, response: Response
    ) -> dict[str, Any]:
        guard_cost(request, "detector")
        owner_id = session_id(request, response)
        if payload.mode == "replay" and not payload.as_of:
            raise HTTPException(status_code=400, detail="replay requires explicit as_of")
        effective_as_of = validated_as_of(payload.as_of)
        anchors = (
            await asyncio.to_thread(store.list_anchors)
            if payload.use_anchors
            else []
        )
        if payload.mode == "replay":

            async def _anchor_fetcher(anchor: Anchor, target: str) -> Any:
                return await replay_anchor_result(store, anchor, target)

            replay = StaleAnswerDetector(
                SnapshotSearcher(store, target_time=effective_as_of),
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                concurrency=3,
                llm=llm,
                mode="replay",
                anchor_fetcher=_anchor_fetcher,
            )
            report = await replay.detect(
                payload.answer, as_of=effective_as_of, anchors=anchors
            )
        elif cfg.anchor_live_fetch and anchors:
            allowlist = {
                item.strip().lower()
                for item in cfg.anchor_allowlist.split(",")
                if item.strip()
            }

            async def _live_anchor(anchor: Anchor, target: str) -> Any:
                return await live_anchor_result(anchor, allowlist)

            live_detector = StaleAnswerDetector(
                tavily,
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                concurrency=3,
                llm=llm,
                mode="live",
                anchor_fetcher=_live_anchor,
            )
            report = await live_detector.detect(
                payload.answer,
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                anchors=anchors,
            )
        else:
            report = await detector.detect(
                payload.answer,
                as_of=effective_as_of,
                max_claims=payload.max_claims,
                anchors=anchors,
            )
        report = report.model_copy(update={"owner_id": owner_id})
        await asyncio.to_thread(store.save_detector_report, report)
        return report.model_dump(mode="json")

    @app.get("/api/detector/{report_id}")
    @app.get("/freshness/reports/{report_id}")
    async def get_detector_report(report_id: str, request: Request) -> dict[str, Any]:
        report = await asyncio.to_thread(store.get_detector_report, report_id)
        if report is None or not can_access(report.owner_id, request):
            raise HTTPException(status_code=404, detail="report not found")
        return report.model_dump(mode="json")

    @app.get("/freshness/reports/{report_id}/receipt")
    async def get_receipt(report_id: str, request: Request) -> dict[str, Any]:
        report = await asyncio.to_thread(store.get_detector_report, report_id)
        if report is None or not can_access(report.owner_id, request):
            raise HTTPException(status_code=404, detail="report not found")
        return build_report_receipt(report).model_dump(mode="json")

    @app.get("/freshness/reports")
    async def list_detector_reports(
        request: Request, limit: int = 20
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        if is_admin(request):
            reports = await asyncio.to_thread(
                store.list_detector_reports, limit=limit
            )
        else:
            reports = await asyncio.to_thread(
                store.list_detector_reports,
                limit=limit,
                owner_id=session_id(request),
            )
        return {
            "reports": [
                {
                    "id": report.id,
                    "as_of": report.as_of,
                    "overall_score": report.overall_score,
                    "stale_claims": report.stale_claims,
                    "claims": len(report.claims),
                    "created_at": report.created_at,
                }
                for report in reports
            ]
        }

    @app.get("/freshness/reports/{report_id}/export")
    async def export_detector_report(
        report_id: str, request: Request
    ) -> dict[str, Any]:
        report = await asyncio.to_thread(store.get_detector_report, report_id)
        if report is None or not can_access(report.owner_id, request):
            raise HTTPException(status_code=404, detail="report not found")
        lines = [
            f"# Freshness Report {report.id}",
            "",
            f"- as_of: {report.as_of}",
            f"- overall: {report.overall_score}",
            f"- claims: {len(report.claims)} / stale: {report.stale_claims}",
            f"- policy: {report.policy_version} / weights: {report.weights_version}",
            "",
        ]
        verdicts = {v.claim_id: v for v in report.verdicts}
        for claim in report.claims:
            verdict = verdicts.get(claim.id)
            lines.append(f"## {claim.text}")
            lines.append(
                f"- type: {claim.type} / sensitivity: {claim.temporal_sensitivity}"
            )
            if verdict:
                lines.append(
                    f"- status: {verdict.status} / score: {verdict.score} "
                    f"/ confidence: {verdict.confidence}"
                )
                lines.append(f"- rationale: {verdict.rationale}")
                if verdict.suggestion:
                    lines.append(f"- suggestion: {verdict.suggestion}")
                for ev in verdict.evidence:
                    lines.append(
                        f"  - [{ev.relation}] {ev.title or ev.url} "
                        f"({ev.published_at or 'unknown'}, T{ev.tier})"
                    )
            lines.append("")
        return {"markdown": "\n".join(lines)}

    @app.post("/freshness/anchors", status_code=201)
    async def create_anchor(payload: AnchorCreate, request: Request) -> dict[str, Any]:
        guard_cost(request, "anchor")
        if not cfg.public_anchor_writes and not is_admin(request):
            raise HTTPException(status_code=403, detail="anchor writes require admin")
        parsed = urlsplit(payload.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise HTTPException(status_code=400, detail="anchor url must be http(s)")
        if parsed.username or parsed.password:
            raise HTTPException(
                status_code=400, detail="anchor url must not contain credentials"
            )
        allowed_hosts = {
            item.strip().lower()
            for item in cfg.anchor_create_allowlist.split(",")
            if item.strip()
        }
        if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
            raise HTTPException(status_code=400, detail="anchor host not allowed")
        snapshots = await asyncio.to_thread(
            store.list_snapshots_for_url, payload.url, 1
        )
        latest = snapshots[0] if snapshots else None
        anchor = Anchor(
            id=f"anc_{uuid.uuid4().hex[:12]}",
            claim_key=claim_key(payload.claim_text),
            claim_text=payload.claim_text,
            url=payload.url,
            source_tier=payload.source_tier,
            last_value=payload.last_value,
            content_hash=payload.content_hash
            or (latest.content_hash if latest else ""),
            published_at=payload.published_at
            or (latest.published_at if latest else None),
            temporal_sensitivity=payload.temporal_sensitivity,
        )
        await asyncio.to_thread(store.save_anchor, anchor)
        return anchor.model_dump(mode="json")

    @app.get("/freshness/anchors")
    async def list_anchors(claim_key: str | None = None) -> dict[str, Any]:
        anchors = await asyncio.to_thread(store.list_anchors, claim_key=claim_key)
        return {"anchors": [anchor.model_dump(mode="json") for anchor in anchors]}

    @app.get("/freshness/compare")
    async def compare_freshness_reports(
        left_id: str, right_id: str, request: Request
    ) -> dict[str, Any]:
        left, right = await asyncio.gather(
            asyncio.to_thread(store.get_detector_report, left_id),
            asyncio.to_thread(store.get_detector_report, right_id),
        )
        if (
            left is None
            or right is None
            or not can_access(left.owner_id, request)
            or not can_access(right.owner_id, request)
        ):
            raise HTTPException(status_code=404, detail="report not found")
        return compare_reports(left, right).model_dump(mode="json")

    @app.post("/admin/anchors/revalidate")
    async def admin_revalidate(
        request: Request, payload: RevalidateRequest | None = None
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        fetcher = None
        if cfg.anchor_live_fetch:
            allowlist = {
                item.strip().lower()
                for item in cfg.anchor_allowlist.split(",")
                if item.strip()
            }

            async def _live(anchor: Anchor, target: str) -> Any:
                return await live_anchor_result(anchor, allowlist)

            fetcher = _live
        observations = await revalidate_due(
            store,
            fetcher=fetcher,
            discovery=discovery,
            limit=payload.limit if payload else 50,
            auto_update=cfg.accuracy_auto_update,
        )
        return {
            "checked": len(observations),
            "changed": sum(1 for item in observations if item.status == "changed"),
            "unreachable": sum(
                1 for item in observations if item.status == "unreachable"
            ),
            "observations": [item.model_dump(mode="json") for item in observations],
        }

    @app.post("/admin/anchors/{anchor_id}/candidates", status_code=201)
    async def create_anchor_candidate(
        anchor_id: str, payload: CandidateCreate, request: Request
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        anchor = await asyncio.to_thread(store.get_anchor, anchor_id)
        if anchor is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        observations = [
            GateObservation(
                url=item.url,
                source_tier=item.source_tier,
                independent_group=item.independent_group
                or independent_group_from_url(item.url),
                value=item.value,
                published_at=item.published_at,
                content_hash=item.content_hash,
                reachable=item.reachable,
            )
            for item in payload.observations
        ]
        gate = evaluate_gate(
            anchor_value=anchor.last_value,
            anchor_published_at=anchor.published_at,
            observations=observations,
            claim_text=anchor.claim_text,
        )
        existing = await asyncio.to_thread(
            store.find_anchor_candidate,
            anchor.id,
            gate.normalized_new,
            gate.decision.value,
        )
        if existing is not None:
            return existing.model_dump(mode="json")
        reachable = [item for item in observations if item.reachable and item.value]
        best = (
            max(reachable, key=lambda item: item.published_at or "")
            if reachable
            else None
        )
        candidate = AnchorCandidate(
            id=f"cand_{uuid.uuid4().hex[:12]}",
            anchor_id=anchor.id,
            claim_key=anchor.claim_key,
            old_value=anchor.last_value,
            new_value=best.value if best else "",
            normalized_old=gate.normalized_old,
            normalized_new=gate.normalized_new,
            evidence=[
                CandidateEvidence(
                    url=item.url,
                    source_tier=item.source_tier,
                    independent_group=item.independent_group,
                    value=item.value,
                    published_at=item.published_at,
                    content_hash=item.content_hash,
                )
                for item in observations
            ],
            gate_decision=gate.decision.value,
            gate_reason=gate.reason,
            gate_version="accuracy-gate-v0",
            confidence=gate.confidence,
        )
        await asyncio.to_thread(store.save_anchor_candidate, candidate)

        if gate.decision.value == "no_change":
            candidate = candidate.model_copy(
                update={"accuracy_status": "no_change", "decided_at": utcnow_iso()}
            )
            await asyncio.to_thread(store.update_anchor_candidate, candidate)
        elif gate.decision.value == "reject":
            candidate = candidate.model_copy(
                update={
                    "accuracy_status": "rejected",
                    "decided_at": utcnow_iso(),
                    "decided_by": "gate",
                }
            )
            await asyncio.to_thread(store.update_anchor_candidate, candidate)
        elif gate.decision.value == "auto_update" and cfg.accuracy_auto_update:
            if best is None:
                raise HTTPException(status_code=400, detail="no usable observation")
            candidate = await asyncio.to_thread(
                apply_candidate,
                store,
                candidate,
                status="auto_applied",
                decided_by="auto-gate",
            )
        return candidate.model_dump(mode="json")

    @app.get("/admin/anchors/candidates")
    async def list_anchor_candidates(
        request: Request, status: str | None = None
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        candidates = await asyncio.to_thread(
            store.list_anchor_candidates, status=status
        )
        return {"candidates": [item.model_dump(mode="json") for item in candidates]}

    @app.post("/admin/anchors/candidates/{candidate_id}/approve")
    async def approve_anchor_candidate(
        candidate_id: str, request: Request
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        candidate = await asyncio.to_thread(store.get_anchor_candidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        if candidate.accuracy_status != "pending":
            raise HTTPException(status_code=409, detail="candidate is not pending")
        anchor = await asyncio.to_thread(store.get_anchor, candidate.anchor_id)
        if anchor is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        if anchor.status != "active":
            raise HTTPException(status_code=409, detail="anchor is no longer active")
        if not candidate.evidence:
            raise HTTPException(status_code=400, detail="candidate has no evidence")
        updated = await asyncio.to_thread(
            apply_candidate,
            store,
            candidate,
            status="approved",
            decided_by="admin",
        )
        return updated.model_dump(mode="json")

    @app.post("/admin/anchors/candidates/{candidate_id}/reject")
    async def reject_anchor_candidate(
        candidate_id: str, request: Request
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        candidate = await asyncio.to_thread(store.get_anchor_candidate, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        if candidate.accuracy_status != "pending":
            raise HTTPException(status_code=409, detail="candidate is not pending")
        updated = candidate.model_copy(
            update={
                "accuracy_status": "rejected",
                "decided_at": utcnow_iso(),
                "decided_by": "admin",
            }
        )
        await asyncio.to_thread(store.update_anchor_candidate, updated)
        return updated.model_dump(mode="json")

    @app.get("/admin/anchors/audit")
    async def admin_anchor_audit(
        request: Request, limit: int = 100
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        audit = await asyncio.to_thread(
            store.list_anchor_audit, limit=max(1, min(limit, 500))
        )
        return {"audit": audit}

    @app.get("/admin/anchors")
    async def admin_list_anchors(request: Request) -> dict[str, Any]:
        _require_admin(request, cfg)
        anchors = await asyncio.to_thread(
            store.list_anchors, active_only=False, limit=500
        )
        return {"anchors": [anchor.model_dump(mode="json") for anchor in anchors]}

    @app.post("/admin/anchors/{anchor_id}/rollback")
    async def admin_rollback_anchor(
        anchor_id: str, request: Request
    ) -> dict[str, Any]:
        _require_admin(request, cfg)
        anchor = await asyncio.to_thread(store.get_anchor, anchor_id)
        if anchor is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        if anchor.status != "active" or not anchor.supersedes:
            raise HTTPException(
                status_code=409, detail="anchor is not an active replacement"
            )
        result = await asyncio.to_thread(store.rollback_anchor, anchor_id)
        if result is None:
            raise HTTPException(status_code=409, detail="rollback failed")
        restored, rolled_back = result
        rolled_candidates = await asyncio.to_thread(
            store.mark_candidates_rolled_back, rolled_back.id
        )
        audit_id = await asyncio.to_thread(
            store.save_anchor_audit,
            "rollback",
            rolled_back.id,
            related_id=restored.id,
            details={"rolled_back_candidates": rolled_candidates},
        )
        return {
            "restored": restored.model_dump(mode="json"),
            "rolled_back": rolled_back.model_dump(mode="json"),
            "rolled_back_candidates": rolled_candidates,
            "audit_id": audit_id,
        }
