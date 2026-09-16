"""Schema versioning. Transparent, ordered migrations over a single local DB.

A single ``schema_version`` row tracks the applied version. Version 1 is the full
initial schema (``schema.sql``). Future schema changes append a numbered step to
``_MIGRATIONS`` — never edit an already-shipped step.
"""

from __future__ import annotations

import importlib.resources as resources
import sqlite3
from collections.abc import Callable

CURRENT_VERSION = 7


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


def _migrate_to_3(conn: sqlite3.Connection) -> None:
    """v3: admin_audit log for the Admin Center (key changes, backups, restores, etc.)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS admin_audit ("
        "id INTEGER PRIMARY KEY, ts TEXT NOT NULL, actor TEXT, "
        "action TEXT NOT NULL, detail TEXT)"
    )


def _migrate_to_4(conn: sqlite3.Connection) -> None:
    """v4: clinician.disabled flag (disabled accounts can't log in). Idempotent."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(clinician)").fetchall()]
    if "disabled" not in cols:
        conn.execute("ALTER TABLE clinician ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")


def _migrate_to_5(conn: sqlite3.Connection) -> None:
    """v5: cue_dwell table — per-cue viewing time tracking."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cue_dwell ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE, "
        "cue_config_id INTEGER REFERENCES cue_config(id), "
        "start_sec INTEGER NOT NULL, "
        "end_sec INTEGER NOT NULL, "
        "dwell_sec INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cue_dwell_session ON cue_dwell(session_id)"
    )


def _migrate_to_6(conn: sqlite3.Connection) -> None:
    """v6: session mode system, neutral cue flag, and craving weight."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(session)").fetchall()]
    if "mode" not in cols:
        conn.execute("ALTER TABLE session ADD COLUMN mode TEXT NOT NULL DEFAULT 'intense'")
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cue_config)").fetchall()]
    if "is_neutral" not in cols:
        conn.execute("ALTER TABLE cue_config ADD COLUMN is_neutral INTEGER NOT NULL DEFAULT 0")
    if "craving_weight" not in cols:
        conn.execute("ALTER TABLE cue_config ADD COLUMN craving_weight REAL")


def _migrate_to_7(conn: sqlite3.Connection) -> None:
    """v7: cue exposure counter for backlog rotation."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cue_config)").fetchall()]
    if "exposure_count" not in cols:
        conn.execute("ALTER TABLE cue_config ADD COLUMN exposure_count INTEGER NOT NULL DEFAULT 0")


# Ordered: index i upgrades the DB to version (i + 1).
_MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    _migrate_to_1,
    _migrate_to_2,
    _migrate_to_3,
    _migrate_to_4,
    _migrate_to_5,
    _migrate_to_6,
    _migrate_to_7,
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
