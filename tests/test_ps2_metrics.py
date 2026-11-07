from __future__ import annotations

from yai_scout.benchmark.runner import FailureInjection
from yai_scout.benchmark.scoring import leaderboard
from yai_scout.domain.models import AgentAnswer, TaskResult


def test_failure_scenarios_are_labeled() -> None:
    injection = FailureInjection(
        enabled=True,
        rate=0.2,
        modes=["tool_timeout", "model_unavailable", "misleading_instruction"],
    )
    assert injection.modes == [
        "tool_timeout",
        "model_unavailable",
        "misleading_instruction",
    ]


def test_ps2_metrics_are_aggregated() -> None:
    results = [
        TaskResult(
            task_id="t1",
            agent_id="a",
            answer=AgentAnswer(text="1000", tokens=100, latency_s=1.0, cost_usd=0.01),
            numeric_accuracy=1.0,
            steps=3,
            tool_calls=2,
        ),
        TaskResult(
            task_id="t2",
            agent_id="a",
            answer=AgentAnswer(text="wrong", tokens=200, latency_s=3.0, cost_usd=0.02),
            numeric_accuracy=0.0,
            steps=5,
            tool_calls=1,
        ),
    ]
    row = leaderboard(results)[0]
    assert row["task_success_rate"] == 0.5
    assert row["avg_steps"] == 4.0
    assert row["avg_tool_calls"] == 1.5
    assert row["avg_tokens"] == 150
