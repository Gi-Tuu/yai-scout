"""SQLite connection and transaction primitives."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            yield self.conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    @contextmanager
    def atomic(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    @contextmanager
    def ddl(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            yield self.conn

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def ping(self) -> None:
        with self.lock:
            self.conn.execute("SELECT 1").fetchone()


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @property
    def _conn(self) -> sqlite3.Connection:
        return self.db.conn

    @property
    def _lock(self) -> threading.RLock:
        return self.db.lock

    @property
    def path(self) -> str:
        return self.db.path
