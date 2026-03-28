"""SQLite connection helpers backed by explicit migrations."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from config.settings import DB_PATH as DEFAULT_DB_PATH
from docintel.db.migrations import apply_migrations


def resolve_db_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the active SQLite path, honoring explicit overrides first."""
    if db_path is not None:
        return Path(db_path)
    env_override = os.environ.get("DOCINTEL_DB_PATH")
    if env_override:
        return Path(env_override)
    return Path(DEFAULT_DB_PATH)


def get_connection(
    db_path: str | os.PathLike[str] | None = None,
    *,
    query_only: bool = False,
    timeout: int = 30,
) -> sqlite3.Connection:
    """Return a configured SQLite connection."""
    path = resolve_db_path(db_path)
    if not query_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    connect_target = f"file:{path.as_posix()}?mode=ro" if query_only else str(path)
    conn = sqlite3.connect(connect_target, timeout=timeout, uri=query_only)
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    if not query_only:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                conn.close()
                raise
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA foreign_keys=ON")
    if query_only:
        conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str | os.PathLike[str] | None = None) -> Path:
    """Create or migrate the DocIntel database and return its path."""
    path = resolve_db_path(db_path)
    conn = get_connection(path)
    try:
        apply_migrations(conn)
    finally:
        conn.close()
    return path
