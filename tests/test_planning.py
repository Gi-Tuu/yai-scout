from yai_scout.pipeline.planning import build_plan, plan_queries


def test_plan_structure_is_deterministic():
    plan = build_plan("2026 年全球 AI 芯片市场规模", "2026-11-01")
    assert plan.generated_by == "rules"
    assert len(plan.sub_questions) == 3
    assert plan.stop_criteria
    first = plan.sub_questions[0]
    assert first.id == "sq1"
    assert len(first.queries) == 2


def test_plan_queries_dedup_preserves_order():
    plan = build_plan("q", "2026-11-01")
    queries = plan_queries(plan)
    assert len(queries) == 4
    assert len(set(queries)) == len(queries)
    assert queries[0] == "q"
