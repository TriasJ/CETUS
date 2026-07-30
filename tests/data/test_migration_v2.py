"""Existing v1 databases upgrade cleanly to v2 (adds clinician_notes, keeps data)."""

import sqlite3

from cravingcrave.data.database import Database
from cravingcrave.data.migrations import CURRENT_VERSION, _load_schema_sql


def test_v1_to_v2_adds_column_and_preserves_data(tmp_path):
    db_path = tmp_path / "old.db"

    # Build a v1 DB by hand: schema sans the new column, version stamped 1.
    schema_v1 = _load_schema_sql().replace(",\n    clinician_notes   TEXT", "")
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_v1)
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute(
        "INSERT INTO clinician (username, display_name, password_hash, created_at) "
        "VALUES ('u','U','x','t')"
    )
    cid = conn.execute("SELECT id FROM clinician").fetchone()[0]
    conn.execute("INSERT INTO patient (code, created_at, created_by) VALUES ('PT-V1','t',?)", (cid,))
    pid = conn.execute("SELECT id FROM patient").fetchone()[0]
    conn.execute(
        "INSERT INTO session (patient_id, clinician_id, substance, started_at, app_version) "
        "VALUES (?,?,?,?,?)",
        (pid, cid, "alcohol", "t", "1.0"),
    )
    conn.commit()
    conn.close()

    # Opening with the current Database runs the v1->v2 migration.
    db = Database(str(db_path))
    assert db.conn.execute("SELECT version FROM schema_version").fetchone()[0] == CURRENT_VERSION
    cols = [r[1] for r in db.conn.execute("PRAGMA table_info(session)").fetchall()]
    assert "clinician_notes" in cols
    assert db.conn.execute("SELECT COUNT(*) FROM session WHERE substance='alcohol'").fetchone()[0] == 1
    assert db.conn.execute("SELECT clinician_notes FROM session").fetchone()[0] is None
