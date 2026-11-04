"""Admin anchor/candidate routes."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from ..api.limits import UsageLimiter
from ..config import Settings
from ..detector.accuracy_gate import GateObservation, evaluate_gate
from ..detector.candidates import apply_candidate, independent_group_from_url
from ..detector.discovery import CachedDiscovery
from ..detector.revalidate import revalidate_due
from ..domain.models import (
    Anchor,
    AnchorCandidate,
    CandidateEvidence,
    utcnow_iso,
)
from ..sources.anchor import live_anchor_result
from ..store import Store


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


def _require_xff_debug(request: Request, cfg: Settings) -> None:
    if not cfg.xff_debug_token:
        raise HTTPException(status_code=404, detail="diagnostic endpoint disabled")
    supplied = request.headers.get("x-xff-debug", "")
    if supplied != cfg.xff_debug_token:
        raise HTTPException(status_code=401, detail="unauthorized")


def register_admin_routes(
    app: FastAPI,
    *,
    cfg: Settings,
    store: Store,
    discovery: CachedDiscovery,
) -> None:
    @app.get("/admin/debug/request", include_in_schema=False)
    async def admin_debug_request(request: Request) -> dict[str, Any]:
        """One-off XFF/proxy inspection; disabled unless XFF_DEBUG_TOKEN is set."""
        _require_xff_debug(request, cfg)
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote = request.client.host if request.client else "unknown"
        return {
            "client_host": remote,
            "client_port": request.client.port if request.client else None,
            "resolved_client_key": UsageLimiter.client_key(headers, remote),
            "x_forwarded_for": headers.get("x-forwarded-for", ""),
            "x_forwarded_for_chain": [
                item.strip() for item in headers.get("x-forwarded-for", "").split(",")
                if item.strip()
            ],
            "forwarded": headers.get("forwarded", ""),
            "x_real_ip": headers.get("x-real-ip", ""),
            "cf_connecting_ip": headers.get("cf-connecting-ip", ""),
            "true_client_ip": headers.get("true-client-ip", ""),
            "x_forwarded_proto": headers.get("x-forwarded-proto", ""),
            "host": headers.get("host", ""),
            "header_names": sorted(headers),
        }

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
