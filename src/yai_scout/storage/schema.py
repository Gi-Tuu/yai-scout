"""Schema definition and initialization."""

from __future__ import annotations

from .db import Database
from .migrations import Migrations

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_task (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    as_of TEXT NOT NULL,
    status TEXT NOT NULL,
    owner_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    finished_at TEXT,
    error TEXT,
    report_md TEXT,
    stats_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS plan (
    task_id TEXT PRIMARY KEY REFERENCES research_task(id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    tier INTEGER NOT NULL DEFAULT 3,
    tier_reason TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL DEFAULT 0,
    snippet TEXT NOT NULL DEFAULT '',
    UNIQUE (task_id, canonical_url)
);
CREATE INDEX IF NOT EXISTS idx_source_task ON source(task_id);
CREATE TABLE IF NOT EXISTS run_event (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_task ON run_event(task_id, seq);
CREATE TABLE IF NOT EXISTS cost_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES research_task(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    unit TEXT NOT NULL,
    amount REAL NOT NULL,
    credits REAL NOT NULL DEFAULT 0,
    usd_estimate REAL NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detector_report (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT '',
    answer TEXT NOT NULL,
    as_of TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bench_session (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    manifest_json TEXT NOT NULL DEFAULT '{}',
    result_hash TEXT,
    supersedes TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS bench_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES bench_session(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS anchor (
    id TEXT PRIMARY KEY,
    claim_key TEXT NOT NULL,
    claim_key_v2 TEXT NOT NULL DEFAULT '',
    claim_key_version INTEGER NOT NULL DEFAULT 1,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_claim ON anchor(claim_key);
CREATE TABLE IF NOT EXISTS anchor_candidate (
    id TEXT PRIMARY KEY,
    anchor_id TEXT NOT NULL REFERENCES anchor(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_candidate_anchor ON anchor_candidate(anchor_id);
CREATE INDEX IF NOT EXISTS idx_anchor_candidate_status ON anchor_candidate(status);
CREATE TABLE IF NOT EXISTS anchor_observation (
    id TEXT PRIMARY KEY,
    anchor_id TEXT NOT NULL REFERENCES anchor(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    content_changed INTEGER NOT NULL DEFAULT 0,
    observed_hash TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_observation_anchor ON anchor_observation(anchor_id);
CREATE TABLE IF NOT EXISTS anchor_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    anchor_id TEXT NOT NULL,
    related_id TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anchor_audit_anchor ON anchor_audit(anchor_id, id);
CREATE TABLE IF NOT EXISTS snapshot (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT 'live',
    content_hash TEXT NOT NULL DEFAULT '',
    raw_path TEXT NOT NULL DEFAULT '',
    text_path TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    updated_at TEXT,
    fetched_at TEXT NOT NULL,
    tier INTEGER NOT NULL DEFAULT 3,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bench_result_session ON bench_result(session_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_url ON snapshot(url, fetched_at);
"""


def initialize(db: Database) -> None:
    with db.ddl():
        if db.path != ":memory:":
            db.conn.execute("PRAGMA journal_mode=WAL")
        db.conn.executescript(SCHEMA)
    Migrations(db).apply()
    with db.ddl():
        db.conn.execute("PRAGMA foreign_keys=ON")
