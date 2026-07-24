"""Schema versioning. Transparent, ordered migrations over a single local DB.

A single ``schema_version`` row tracks the applied version. Version 1 is the full
initial schema (``schema.sql``). Future schema changes append a numbered step to
``_MIGRATIONS`` — never edit an already-shipped step.
"""

from __future__ import annotations

import importlib.resources as resources
import sqlite3
from collections.abc import Callable

CURRENT_VERSION = 2


def _load_schema_sql() -> str:
    return (
        resources.files("cravingcrave.data")
        .joinpath("schema.sql")
        .read_text(encoding="utf-8")
    )


def _migrate_to_1(conn: sqlite3.Connection) -> None:
    conn.executescript(_load_schema_sql())


def _migrate_to_2(conn: sqlite3.Connection) -> None:
    """v2: clinician_notes column on session. Idempotent — fresh v2 DBs already have it."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(session)").fetchall()]
    if "clinician_notes" not in cols:
        conn.execute("ALTER TABLE session ADD COLUMN clinician_notes TEXT")


# Ordered: index i upgrades the DB to version (i + 1).
_MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    _migrate_to_1,
    _migrate_to_2,
]


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    ver = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    return int(ver[0]) if ver else 0


def apply_migrations(conn: sqlite3.Connection) -> None:
    version = _current_version(conn)
    for step in range(version, len(_MIGRATIONS)):
        _MIGRATIONS[step](conn)
    if version < CURRENT_VERSION:
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (CURRENT_VERSION,))
        conn.commit()
