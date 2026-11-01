import sys
from pathlib import Path

from yai_scout.benchmark.adapters import CLIAdapter, PythonAdapter
from yai_scout.benchmark.dataset import load_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _task():
    return next(task for task in load_tasks() if task.id == "b_tavily_free_credits")


async def test_python_adapter_runs_in_process():
    adapter = PythonAdapter("py", "Python Agent", "examples.python_agent:answer")
    answer = await adapter.answer(_task())
    assert answer.text.startswith("Tavily")
    assert answer.citations
    assert answer.error is None


async def test_cli_adapter_runs_subprocess():
    script = ROOT / "examples" / "cli_agent.py"
    adapter = CLIAdapter("cli", "CLI Agent", [sys.executable, str(script)])
    answer = await adapter.answer(_task())
    assert answer.text.startswith("Tavily")
    assert answer.citations
    assert answer.error is None
