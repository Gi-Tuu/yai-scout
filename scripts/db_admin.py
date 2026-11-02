# ruff: noqa: E501
"""Offline SQLite operations: integrity check, backup, restore, vacuum.

Usage:
    python scripts/db_admin.py check  --db data/scout.sqlite3
    python scripts/db_admin.py backup --db data/scout.sqlite3 \\\n        --out backups/scout-2026-11-02.sqlite3
    python scripts/db_admin.py restore --backup backups/scout-....sqlite3 --db data/scout.sqlite3 --force
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path


def _connect(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(path)


def integrity_check(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"database not found: {path}")
    conn = _connect(path, read_only=True)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "unknown"
    finally:
        conn.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(db: Path, out: Path) -> None:
    if not db.is_file():
        raise SystemExit(f"database not found: {db}")
    if out.exists():
        raise SystemExit(f"refusing to overwrite backup: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    source = _connect(db, read_only=True)
    target = _connect(out)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    result = integrity_check(out)
    if result != "ok":
        raise SystemExit(f"backup integrity check failed: {result}")
    print(f"backup={out} bytes={out.stat().st_size} sha256={sha256(out)} integrity={result}")


def restore(backup_path: Path, db: Path, *, force: bool) -> None:
    if not backup_path.is_file():
        raise SystemExit(f"backup not found: {backup_path}")
    if db.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing database: {db} (use --force)")
    result = integrity_check(backup_path)
    if result != "ok":
        raise SystemExit(f"backup integrity check failed: {result}")
    db.parent.mkdir(parents=True, exist_ok=True)
    source = _connect(backup_path, read_only=True)
    target = _connect(db)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    print(f"restored={db} integrity={integrity_check(db)}")


def vacuum(db: Path) -> None:
    conn = _connect(db)
    try:
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()
    print(f"vacuumed={db}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--db", required=True, type=Path)
    backup_cmd = sub.add_parser("backup")
    backup_cmd.add_argument("--db", required=True, type=Path)
    backup_cmd.add_argument("--out", required=True, type=Path)
    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("--backup", required=True, type=Path)
    restore_cmd.add_argument("--db", required=True, type=Path)
    restore_cmd.add_argument("--force", action="store_true")
    vacuum_cmd = sub.add_parser("vacuum")
    vacuum_cmd.add_argument("--db", required=True, type=Path)

    args = parser.parse_args()
    if args.command == "check":
        result = integrity_check(args.db)
        print(f"integrity={result}")
        return 0 if result == "ok" else 1
    if args.command == "backup":
        backup(args.db, args.out)
        return 0
    if args.command == "restore":
        restore(args.backup, args.db, force=args.force)
        return 0
    vacuum(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


