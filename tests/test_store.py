from yai_scout.domain.models import (
    CostEntry,
    Plan,
    ResearchTask,
    RunEvent,
    SourceRecord,
    Stage,
    SubQuestion,
    TaskStatus,
)
from yai_scout.store import Store


def make_task(task_id: str = "task_1") -> ResearchTask:
    return ResearchTask(id=task_id, question="q", as_of="2026-11-01")


def make_source(task_id: str, canonical: str = "https://a.com/x") -> SourceRecord:
    return SourceRecord(
        id=f"src_{canonical[-1]}",
        task_id=task_id,
        url=canonical,
        canonical_url=canonical,
        domain="a.com",
        title="t",
    )


def test_task_lifecycle():
    store = Store(":memory:")
    task = make_task()
    store.create_task(task)
    assert store.get_task(task.id).status is TaskStatus.PENDING
    store.update_task(task.id, status=TaskStatus.RUNNING)
    store.update_task(task.id, status=TaskStatus.DELIVERED, report_md="# hi", stats={"n": 1})
    got = store.get_task(task.id)
    assert got.status is TaskStatus.DELIVERED
    assert got.report_md == "# hi"
    assert got.stats == {"n": 1}
    store.close()


def test_plan_roundtrip():
    store = Store(":memory:")
    task = make_task()
    store.create_task(task)
    plan = Plan(sub_questions=[SubQuestion(id="sq1", question="q", queries=["a"])])
    store.save_plan(task.id, plan)
    got = store.get_plan(task.id)
    assert got is not None and got.sub_questions[0].id == "sq1"
    store.close()


def test_source_dedupe_and_count():
    store = Store(":memory:")
    task = make_task()
    store.create_task(task)
    assert store.add_source(make_source(task.id)) is True
    assert store.add_source(make_source(task.id)) is False  # canonical 相同
    assert store.count_sources(task.id) == 1
    store.close()


def test_events_and_cost():
    store = Store(":memory:")
    task = make_task()
    store.create_task(task)
    store.append_event(RunEvent(task_id=task.id, stage=Stage.PLANNING, type="stage_started"))
    store.append_event(RunEvent(task_id=task.id, stage=Stage.PLANNING, type="plan_ready"))
    events = store.list_events(task.id)
    assert [e.type for e in events] == ["stage_started", "plan_ready"]
    assert store.list_events(task.id, after_seq=events[0].seq)[0].type == "plan_ready"
    store.add_cost(
        CostEntry(task_id=task.id, provider="tavily", unit="search", amount=1, credits=2)
    )
    store.add_cost(
        CostEntry(task_id=task.id, provider="tavily", unit="search", amount=1, credits=1)
    )
    credits, usd = store.cost_sum(task.id)
    assert credits == 3.0 and usd == 0.0
    store.close()

