"""Pure aggregation for repeated benchmark cells."""

from __future__ import annotations

import statistics

from ..domain.models import TaskResult

Sample = tuple[TaskResult, str | None, list[dict[str, object]]]


def aggregate_samples(samples: list[Sample], repeats: int) -> TaskResult:
    valid_samples = [
        item for item in samples if not item[0].error and item[0].answer.text.strip()
    ]
    scores_pool = valid_samples or samples
    base = max(scores_pool, key=lambda item: item[0].score)
    sample_count = len(valid_samples) or 1
    scores = [item[0].score for item in scores_pool]
    successes = len(valid_samples)
    faults = sorted({fault for _result, fault, _trace in samples if fault})
    trace: list[dict[str, object]] = []
    for _result, _fault, sample_trace in samples:
        trace.extend(sample_trace)
    trace = trace[:100]

    def average(values: list[float | None]) -> float | None:
        usable = [value for value in values if value is not None]
        return round(sum(usable) / len(usable), 4) if usable else None

    aggregate = base[0].model_copy(
        update={
            "score": round(sum(scores) / len(scores), 4),
            "numeric_accuracy": round(
                sum(item[0].numeric_accuracy for item in scores_pool) / sample_count,
                3,
            ),
            "has_citations": any(item[0].has_citations for item in scores_pool),
            "citation_count": round(
                sum(item[0].citation_count for item in scores_pool) / sample_count
            ),
            "freshness_score": average(
                [item[0].freshness_score for item in scores_pool]
            ),
            "stale_claim_rate": average(
                [item[0].stale_claim_rate for item in scores_pool]
            ),
            "claim_coverage": round(
                sum(item[0].claim_coverage for item in scores_pool) / sample_count,
                3,
            ),
            "supported_claim_rate": average(
                [item[0].supported_claim_rate for item in scores_pool]
            ),
            "stable_fact_integrity": average(
                [item[0].stable_fact_integrity for item in scores_pool]
            ),
            "evidence_quality": average(
                [item[0].evidence_quality for item in scores_pool]
            ),
            "repeats": repeats,
            "score_std": (
                round(statistics.pstdev(scores), 4) if len(scores) > 1 else 0.0
            ),
            "answer": base[0].answer.model_copy(
                update={
                    "tokens": round(
                        sum(item[0].answer.tokens for item in scores_pool) / sample_count
                    ),
                    "prompt_tokens": round(
                        sum(item[0].answer.prompt_tokens for item in scores_pool)
                        / sample_count
                    ),
                    "completion_tokens": round(
                        sum(item[0].answer.completion_tokens for item in scores_pool)
                        / sample_count
                    ),
                    "cost_usd": round(
                        sum(item[0].answer.cost_usd for item in scores_pool)
                        / sample_count,
                        6,
                    ),
                    "latency_s": round(
                        sum(item[0].answer.latency_s for item in scores_pool)
                        / sample_count,
                        2,
                    ),
                }
            ),
            "success_rate": round(successes / repeats, 3),
            "faults": faults,
            "trace": trace,
            "samples": [
                {
                    "score": result.score,
                    "numeric_accuracy": result.numeric_accuracy,
                    "freshness_score": result.freshness_score,
                    "stale_claim_rate": result.stale_claim_rate,
                    "latency_s": result.answer.latency_s,
                    "cost_usd": result.answer.cost_usd,
                    "steps": result.steps,
                    "tool_calls": result.tool_calls,
                    "error": result.error,
                    "fault": fault,
                }
                for result, fault, _trace in samples
            ],
            "error": (
                None
                if successes == repeats
                else (
                    base[0].error
                    if repeats == 1
                    else f"{repeats - successes}/{repeats} runs failed"
                )
            ),
        }
    )
    return aggregate
