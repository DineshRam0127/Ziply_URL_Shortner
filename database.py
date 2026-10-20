"""
database.py — SQLite connection and schema initialisation for Ziply.

Uses the Python stdlib sqlite3 module. No ORM required.

DB_PATH behaviour
-----------------
* Default (production): "ziply.db" — a file that persists across restarts.
* Tests set DB_PATH to a temp file path via os.environ BEFORE importing
  app modules. The temp file is cleaned up by the pytest fixture.

The check_same_thread=False flag is set so that connections can be used
across threads (FastAPI routes run in a thread pool).

Schema migrations are applied additively via ALTER TABLE so that an
existing ziply.db is upgraded without data loss.
"""

import os
import sqlite3
from contextlib import contextmanager

_DEFAULT_DB = "ziply.db"

# ── Core table (original schema) ──────────────────────────────────────────────

_CREATE_URLS_SQL = """
CREATE TABLE IF NOT EXISTS urls (
    code        TEXT PRIMARY KEY,
    original    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    alias       TEXT,
    expires_at  TEXT,
    user_id     INTEGER
);
"""

# ── Click-tracking table ───────────────────────────────────────────────────────

_CREATE_CLICKS_SQL = """
CREATE TABLE IF NOT EXISTS clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL REFERENCES urls(code) ON DELETE CASCADE,
    visited_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

_CREATE_CLICKS_IDX = """
CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code);
"""

# ── Users table (prepared for Phase 4 auth) ───────────────────────────────────

_CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Alias unique index ─────────────────────────────────────────────────────────

_CREATE_ALIAS_IDX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_urls_alias
    ON urls(alias) WHERE alias IS NOT NULL;
"""


def _resolved_path(db_path: str | None) -> str:
    """Return the effective database path from the argument or environment."""
    return db_path or os.environ.get("DB_PATH", _DEFAULT_DB)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """
    Additively add columns that may not exist in an older ziply.db.
    ALTER TABLE … ADD COLUMN is a no-op when the column already exists on
    SQLite ≥ 3.37; for older versions we catch OperationalError.
    """
    migrations = [
        "ALTER TABLE urls ADD COLUMN alias TEXT",
        "ALTER TABLE urls ADD COLUMN expires_at TEXT",
        "ALTER TABLE urls ADD COLUMN user_id INTEGER",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists — safe to ignore


def init_db(db_path: str | None = None) -> None:
    """Create the database file and all tables / indexes if they don't exist yet.
    Also applies additive column migrations for existing databases."""
    path = _resolved_path(db_path)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.execute(_CREATE_URLS_SQL)
        _apply_migrations(conn)
        conn.execute(_CREATE_CLICKS_SQL)
        conn.execute(_CREATE_CLICKS_IDX)
        conn.execute(_CREATE_USERS_SQL)
        conn.execute(_CREATE_ALIAS_IDX)
        conn.commit()


@contextmanager
def get_connection(db_path: str | None = None):
    """
    Context manager that yields an open sqlite3 connection and commits /
    rolls back automatically.

    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    path = _resolved_path(db_path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
