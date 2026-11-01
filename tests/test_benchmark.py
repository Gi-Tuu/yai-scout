import asyncio

from yai_scout.benchmark.adapters import LLMAgentAdapter, MockAdapter
from yai_scout.benchmark.dataset import load_dataset, load_tasks
from yai_scout.benchmark.runner import BenchmarkRunner
from yai_scout.benchmark.scoring import (
    composite_score,
    leaderboard,
    match_gold,
    numeric_accuracy,
    pareto_frontier,
)
from yai_scout.domain.models import BenchSession, TaskResult
from yai_scout.llm import LLMResult
from yai_scout.retrieval.tavily import SearchResult
from yai_scout.store import Store


def test_match_gold_numbers_and_strings():
    assert match_gold("1000", "每月 1,000 credits")
    assert match_gold("0.30", "价格是 $0.30 / 百万 token")
    assert not match_gold("0.30", "价格是 0.15")
    assert match_gold("Apache-2.0", "licensed under Apache-2.0")
    assert not match_gold("Apache-2.0", "MIT license")


def test_numeric_accuracy_partial():
    assert numeric_accuracy(["1000", "2"], "免费 1,000 credits，advanced 每次 1") == 0.5


def test_composite_bounds():
    assert 0 <= composite_score(
        numeric=0, has_citations=False, stale_rate=1.0, completed=False, cost_usd=1.0
    ) <= 1
    assert composite_score(
        numeric=1, has_citations=True, stale_rate=0.0, completed=True, cost_usd=0.0
    ) > 0.8


def test_leaderboard_orders_by_score():
    rows = leaderboard(
        [
            TaskResult(task_id="t1", agent_id="a", answer={"text": "x"}, score=0.9),  # type: ignore[arg-type]
            TaskResult(task_id="t2", agent_id="a", answer={"text": "x"}, score=0.8),  # type: ignore[arg-type]
            TaskResult(task_id="t1", agent_id="b", answer={"text": "x"}, score=0.2),  # type: ignore[arg-type]
        ]
    )
    assert rows[0]["agent_id"] == "a"
    assert rows[0]["runs"] == 2


async def test_llm_agent_adapter_returns_answer_and_citations():
    class FakeTavily:
        async def search(self, query: str, **kwargs):  # type: ignore[no-untyped-def]
            return [
                SearchResult(
                    title="Tavily pricing",
                    url="https://docs.tavily.com/documentation/api-credits",
                    content="1,000 free credits per month.",
                    published_date="Tue, 28 Oct 2026 00:00:00 GMT",
                )
            ], 1.0

    class FakeLLM:
        available = True

        async def chat_text(self, system: str, user: str, **kwargs):  # type: ignore[no-untyped-def]
            return LLMResult(
                text="Tavily gives 1,000 free credits per month [1].",
                prompt_tokens=300,
                completion_tokens=30,
                cost_usd=0.0002,
            )

    adapter = LLMAgentAdapter(FakeTavily(), FakeLLM())  # type: ignore[arg-type]
    task = load_tasks()[0]
    answer = await adapter.answer(task)
    assert answer.text.startswith("Tavily gives")
    assert answer.citations == ["https://docs.tavily.com/documentation/api-credits"]
    assert answer.tokens == 330
    assert answer.cost_usd > 0


def test_dataset_has_24_tasks_and_hidden_split():
    version, tasks = load_dataset()
    assert version.startswith("freshness-bench/")
    assert len(tasks) == 24
    assert sum(1 for task in tasks if task.hidden) == 3
    assert len(load_tasks()) == 21


def test_pareto_frontier_marks_dominated_agents():
    # 直接构造 leaderboard 输入所需的字段
    results = [
        TaskResult(
            task_id="t1",
            agent_id="good",
            answer={"text": "x"},  # type: ignore[arg-type]
            numeric_accuracy=1.0,
            freshness_score=90,
            score=0.9,
        ),
        TaskResult(
            task_id="t1",
            agent_id="cheap",
            answer={"text": "x"},  # type: ignore[arg-type]
            numeric_accuracy=0.8,
            freshness_score=80,
            score=0.8,
        ),
        TaskResult(
            task_id="t1",
            agent_id="weak",
            answer={"text": "x"},  # type: ignore[arg-type]
            numeric_accuracy=0.4,
            freshness_score=40,
            score=0.4,
        ),
    ]
    frontier = pareto_frontier(results)
    assert "weak" not in frontier["frontier"]
    assert "good" in frontier["frontier"]


async def test_runner_completes_with_mock_adapters():
    store = Store(":memory:")
    adapters = {
        "mock_good": MockAdapter("mock_good", "Mock good", good=True),
        "mock_stale": MockAdapter("mock_stale", "Mock stale", good=False),
    }
    runner = BenchmarkRunner(
        store, adapters, detector=None, concurrency=2, detect_freshness=False
    )
    session = runner.start(
        ["mock_good", "mock_stale"], ["b_tavily_free_credits", "b_bifrost_license"]
    )
    assert isinstance(session, BenchSession)

    current = session
    for _ in range(100):
        loaded = store.get_bench_session(session.id)
        assert loaded is not None
        current = loaded
        if current.status != "running":
            break
        await asyncio.sleep(0.02)

    assert current.status == "done"
    results = store.list_bench_results(session.id)
    assert len(results) == 4
    good = [r for r in results if r.agent_id == "mock_good"]
    assert all(r.numeric_accuracy == 1.0 for r in good)
    stale = [r for r in results if r.agent_id == "mock_stale"]
    assert all(r.numeric_accuracy == 0.0 for r in stale)
    store.close()
