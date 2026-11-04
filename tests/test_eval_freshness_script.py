from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eval_freshness_calibrate_runs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/eval_freshness.py", "--calibrate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "top weights" in result.stdout
    assert "acc=0.950" in result.stdout
