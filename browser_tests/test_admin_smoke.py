"""Real-browser smoke test for the token-gated admin actions.

Run explicitly:

    pytest -q browser_tests

The normal `tests` suite does not depend on a browser.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from yai_scout.domain.models import (  # noqa: E402
    Anchor,
    AnchorCandidate,
    CandidateEvidence,
)
from yai_scout.store import Store  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _seed(db_path: Path) -> None:
    store = Store(db_path)
    store.save_anchor(Anchor(
        id="old",
        claim_key="smoke claim",
        claim_text="smoke claim",
        url="https://example.com/old",
        source_tier=1,
        last_value="old value",
    ))
    store.save_anchor(Anchor(
        id="new",
        claim_key="smoke claim",
        claim_text="smoke claim",
        url="https://example.com/new",
        source_tier=1,
        last_value="new value",
        supersedes="old",
    ))
    store.save_anchor_candidate(AnchorCandidate(
        id="c1",
        anchor_id="old",
        claim_key="smoke claim",
        old_value="old value",
        new_value="new value",
        gate_decision="review",
        gate_reason="smoke",
        evidence=[CandidateEvidence(
            url="https://example.com/new",
            source_tier=1,
            independent_group="official",
            value="new value",
        )],
        accuracy_status="pending",
    ))
    store.close()


@pytest.mark.browser
def test_admin_rollback_and_approve_in_browser(tmp_path: Path) -> None:
    db_path = tmp_path / "admin-smoke.sqlite3"
    _seed(db_path)
    port = _free_port()
    env = os.environ.copy()
    env.update({
        "DB_PATH": str(db_path),
        "ADMIN_TOKEN": "smoke-token",
        "PUBLIC_ANCHOR_WRITES": "true",
        "DEMO_LIMITS_ENABLED": "false",
        "BENCHMARK_RETENTION_DAYS": "0",
        "XFF_DEBUG_TOKEN": "",
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "yai_scout.api.app:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"{base}/api/healthz", timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        else:
            raise AssertionError("local app did not start")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on(
                "console",
                lambda msg: errors.append(msg.text) if msg.type == "error" else None,
            )
            page.goto(f"{base}/admin", wait_until="networkidle")
            page.fill("#token", "smoke-token")
            page.click("#load")
            page.locator("#status").filter(has_text="anchors=2").wait_for(
                timeout=10000
            )

            page.on("dialog", lambda dialog: dialog.accept())
            page.locator('button[data-rollback="new"]').click()
            page.locator('button[data-rollback="new"]').wait_for(
                state="detached", timeout=10000
            )
            page.locator('button[data-approve="c1"]').click()
            page.locator('button[data-approve="c1"]').wait_for(
                state="detached", timeout=10000
            )
            assert not errors, f"browser errors: {errors}"
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
