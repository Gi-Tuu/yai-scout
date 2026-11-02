from __future__ import annotations

from yai_scout.domain.models import BenchSession, ResearchTask, TaskStatus
from yai_scout.store import Store


def test_interrupted_research_task_is_reconciled_on_restart():
    store = Store(":memory:")
    store.create_task(
        ResearchTask(
            id="task_running",
            question="q",
            as_of="2026-11-01",
            status=TaskStatus.RUNNING,
        )
    )
    store.mark_interrupted_work()
    task = store.get_task("task_running")
    assert task is not None
    assert task.status is TaskStatus.FAILED
    assert "interrupted" in task.error
    store.close()


def test_interrupted_benchmark_session_is_reconciled_on_restart():
    store = Store(":memory:")
    store.create_bench_session(BenchSession(id="bench_running", status="running"))
    store.mark_interrupted_work()
    session = store.get_bench_session("bench_running")
    assert session is not None
    assert session.status == "failed"
    assert "interrupted" in (session.error or "")
    store.close()
