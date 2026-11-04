from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_app_import_does_not_create_default_database(tmp_path: Path) -> None:
    db_path = tmp_path / "should_not_exist.sqlite3"
    env = {**os.environ, "DB_PATH": str(db_path)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import yai_scout.api.app as m; "
            "assert 'app' not in m.__dict__, 'import created app'; "
            "print('ok')",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
    assert not db_path.exists()
