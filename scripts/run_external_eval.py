"""Run baselines over the frozen external dev set.

B0/B1/B2/B5 use the same evidence package. B3 is LLM-only on the same evidence.
B4 retrieves independently and is reported separately.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from yai_scout.config import Settings
from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.detector.relation import classify_relation
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    TemporalSensitivity,
)
from yai_scout.llm import LLMClient
from yai_scout.retrieval.quality import classify_source
from yai_scout.retrieval.tavily import SearchResult, TavilyClient

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "benchmarks" / "external_v1"
METHODS = (
    "always_fresh",
    "recency_only",
    "citation_only",
    "yais_full",
    "llm_only",
    "retrieval_only",
)
LATEST_RE = re.compile(r"Latest version:\s*(\S+)")
LLM_SYSTEM = """You are a freshness judge. Given one claim and one frozen source,
return JSON only: {"status":"fresh|stale|insufficient","reason":"<short>"}.
Use stale only when the source states a different current value. Do not use
outside knowledge."""


def _rows(path: Path, labels: Path | None = None) -> list[dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if labels is None:
        return rows
    label_map = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in labels.read_text(encoding="utf-8").splitlines()
            if line
        )
    }
    for row in rows:
        row.update(label_map.get(row["id"], {}))
    return rows


def _latest_value(row: dict) -> str | None:
    if not row.get("evidence"):
        return None
    text = (EXTERNAL / row["evidence"][0]["snapshot_path"]).read_text(encoding="utf-8")
    match = LATEST_RE.search(text)
    return match.group(1) if match else None


def _evidence(row: dict, claim: Claim) -> list[EvidenceRef]:
    evidence: list[EvidenceRef] = []
    for item in row["evidence"]:
        snapshot = (EXTERNAL / item["snapshot_path"]).read_text(encoding="utf-8")
        result = SearchResult(
            title=f"{row['source_family']} release history",
            url=item["url"],
            content=snapshot,
            published_date=item.get("published_at"),
        )
        tier, _ = classify_source(item["url"])
        if "pypi.org" in item["url"]:
            tier = 1
        evidence.append(
            EvidenceRef(
                url=item["url"],
                title=result.title,
                domain="pypi.org",
                published_at=item.get("published_at"),
                tier=tier,
                snippet=snapshot[:1200],
                relation=classify_relation(claim, result),
            )
        )
    return evidence


def _claim(row: dict) -> Claim:
    return Claim(
        id=row["id"],
        text=row["claim_text"],
        type=ClaimType(row["claim_type"]),
        target_time=row["as_of"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )


def predict(row: dict, method: str) -> dict:
    as_of = as_of_datetime(row["as_of"])
    claim = _claim(row)
    evidence = _evidence(row, claim)
    base = {
        "id": row["id"],
        "expected": row.get("gold_status"),
        "source_family": row.get("source_family", ""),
        "claim_type": row.get("claim_type", ""),
        "gold_current_value": row.get("gold_current_value"),
        "current_value": _latest_value(row),
    }
    if method == "always_fresh":
        return {**base, "predicted": "fresh"}
    if method == "recency_only":
        fresh = False
        for item in evidence:
            if not item.published_at:
                continue
            published = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            if (as_of - published).days <= 365:
                fresh = True
        return {**base, "predicted": "fresh" if fresh else "insufficient"}
    if method == "citation_only":
        supported = any(item.relation == "supports" for item in evidence)
        return {**base, "predicted": "fresh" if supported else "insufficient"}
    verdict = score_claim(claim, evidence, as_of=as_of, allow_future=False)
    return {
        **base,
        "predicted": verdict.status.value,
        "score": verdict.score,
    }


async def predict_llm(row: dict, client: LLMClient) -> dict:
    claim = _claim(row)
    snapshot = (EXTERNAL / row["evidence"][0]["snapshot_path"]).read_text(encoding="utf-8")
    base = {
        "id": row["id"],
        "expected": row.get("gold_status"),
        "source_family": row.get("source_family", ""),
        "claim_type": row.get("claim_type", ""),
        "gold_current_value": row.get("gold_current_value"),
        "current_value": _latest_value(row),
    }
    payload = await client.chat_json(
        LLM_SYSTEM,
        f"Claim: {claim.text}\nSource:\n{snapshot}",
        max_tokens=120,
    )
    if payload is None:
        return {**base, "predicted": "insufficient", "error": "llm unavailable"}
    data, result = payload
    status = str(data.get("status") or "").lower()
    if status not in {"fresh", "stale", "insufficient"}:
        status = "insufficient"
    return {**base, "predicted": status, "cost_usd": result.cost_usd}


async def predict_retrieval(row: dict, client: TavilyClient) -> dict:
    claim = _claim(row)
    results, credits = await client.search(
        f"{claim.text} latest official", max_results=3
    )
    base = {
        "id": row["id"],
        "expected": row.get("gold_status"),
        "source_family": row.get("source_family", ""),
        "claim_type": row.get("claim_type", ""),
        "gold_current_value": row.get("gold_current_value"),
        "current_value": None,
        "credits": credits,
    }
    if not results:
        return {**base, "predicted": "insufficient"}
    top = results[0]
    relation = classify_relation(claim, top)
    return {
        **base,
        "predicted": "fresh" if relation == "supports" else "insufficient",
        "relation": relation,
    }


async def main_async(args: argparse.Namespace) -> int:
    rows = _rows(Path(args.data), Path(args.labels) if args.labels else None)
    if args.method == "llm_only":
        settings = Settings()
        connection = settings.llm_connection()
        client = LLMClient(
            api_key=str(connection["api_key"]),
            base_url=str(connection["base_url"]),
            model=str(connection["model"]),
            require_key=bool(connection["require_key"]),
            timeout=60.0,
        )
        try:
            predictions = [await predict_llm(row, client) for row in rows]
        finally:
            await client.aclose()
    elif args.method == "retrieval_only":
        settings = Settings()
        client = TavilyClient(
            api_key=settings.tavily_api_key,
            base_url=settings.tavily_base_url,
            allow_keyless=settings.tavily_allow_keyless,
            timeout=settings.tavily_timeout_seconds,
            search_depth="basic",
            max_results=3,
        )
        try:
            predictions = [await predict_retrieval(row, client) for row in rows]
        finally:
            await client.aclose()
    else:
        predictions = [predict(row, args.method) for row in rows]
    payload = {
        "method": args.method,
        "split": Path(args.data).stem,
        "cases": len(predictions),
        "predictions": predictions,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(EXTERNAL / "dev.jsonl"))
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--labels", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
