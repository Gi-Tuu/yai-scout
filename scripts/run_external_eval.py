"""Run deterministic baselines over the frozen external dev set."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from yai_scout.detector.freshness import as_of_datetime, score_claim
from yai_scout.detector.relation import classify_relation
from yai_scout.domain.models import (
    Claim,
    ClaimType,
    EvidenceRef,
    TemporalSensitivity,
)
from yai_scout.retrieval.quality import classify_source
from yai_scout.retrieval.tavily import SearchResult

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "benchmarks" / "external_v1"
METHODS = ("always_fresh", "recency_only", "citation_only", "yais_full")


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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


def predict(row: dict, method: str) -> dict:
    as_of = as_of_datetime(row["as_of"])
    claim = Claim(
        id=row["id"],
        text=row["claim_text"],
        type=ClaimType(row["claim_type"]),
        target_time=row["as_of"],
        temporal_sensitivity=TemporalSensitivity.SENSITIVE,
    )
    evidence = _evidence(row, claim)
    if method == "always_fresh":
        return {"id": row["id"], "expected": row["gold_status"], "predicted": "fresh"}
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
        return {
            "id": row["id"],
            "expected": row["gold_status"],
            "predicted": "fresh" if fresh else "insufficient",
        }
    if method == "citation_only":
        supported = any(item.relation == "supports" for item in evidence)
        return {
            "id": row["id"],
            "expected": row["gold_status"],
            "predicted": "fresh" if supported else "insufficient",
        }
    verdict = score_claim(claim, evidence, as_of=as_of, allow_future=False)
    return {
        "id": row["id"],
        "expected": row["gold_status"],
        "predicted": verdict.status.value,
        "score": verdict.score,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(EXTERNAL / "dev.jsonl"))
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    rows = _rows(Path(args.data))
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


if __name__ == "__main__":
    raise SystemExit(main())
