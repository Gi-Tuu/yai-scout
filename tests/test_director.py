import asyncio

from yai_scout.config import Settings
from yai_scout.domain.models import ResearchTask, TaskStatus
from yai_scout.pipeline.director import ResearchDirector
from yai_scout.retrieval.tavily import SearchResult, TavilyError
from yai_scout.store import Store


class FakeTavily:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    mode = "fake"
    authenticated = False

    async def search(self, query: str, **kwargs) -> tuple[list[SearchResult], float]:
        self.calls += 1
        if self.fail:
            raise TavilyError("boom", status_code=500)
        return (
            [
                SearchResult(
                    title=f"result {self.calls}",
                    url=f"https://site{self.calls}.example.com/a",
                    content="content " * 10,
                    score=0.9,
                )
            ],
            1.0,
        )

    async def aclose(self) -> None:
        pass


async def wait_done(store: Store, task_id: str, timeout: float = 3.0) -> ResearchTask:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        task = store.get_task(task_id)
        assert task is not None
        if task.status in {TaskStatus.DELIVERED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return task
        await asyncio.sleep(0.02)
    raise AssertionError("director did not finish in time")


async def test_director_delivers_sources():
    store = Store(":memory:")
    settings = Settings(db_path=":memory:", max_queries=2, max_concurrency=2)
    director = ResearchDirector(store, FakeTavily(), settings)  # type: ignore[arg-type]
    task = ResearchTask(id="task_t1", question="test question", as_of="2026-11-01")
    store.create_task(task)
    director.start(task)

    done = await wait_done(store, task.id)
    assert done.status is TaskStatus.DELIVERED
    sources = store.list_sources(task.id)
    assert len(sources) >= 2
    assert done.report_md and "已收集来源" in done.report_md
    assert done.stats["sources"] == len(sources)

    types = [e.type for e in store.list_events(task.id)]
    assert "plan_ready" in types
    assert "source_found" in types
    assert "run_finished" in types
    assert "stage_skipped" in types  # 抽取/验证在 G0 显式跳过
    assert store.cost_sum(task.id)[0] == 2.0
    store.close()


async def test_director_marks_failure_when_all_queries_fail():
    store = Store(":memory:")
    settings = Settings(db_path=":memory:", max_queries=2)
    director = ResearchDirector(store, FakeTavily(fail=True), settings)  # type: ignore[arg-type]
    task = ResearchTask(id="task_t2", question="test question", as_of="2026-11-01")
    store.create_task(task)
    director.start(task)

    done = await wait_done(store, task.id)
    assert done.status is TaskStatus.FAILED
    assert done.error and "没有拿到任何来源" in done.error
    assert "run_failed" in [e.type for e in store.list_events(task.id)]
    store.close()


async def test_director_cancel():
    store = Store(":memory:")
    settings = Settings(db_path=":memory:", max_queries=2)
    director = ResearchDirector(store, FakeTavily(), settings)  # type: ignore[arg-type]
    task = ResearchTask(id="task_t3", question="test question", as_of="2026-11-01")
    store.create_task(task)
    director.start(task)
    assert await director.cancel(task.id) is True
    done = await wait_done(store, task.id)
    assert done.status is TaskStatus.CANCELLED
    store.close()


