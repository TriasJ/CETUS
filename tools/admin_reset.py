"""Offline admin recovery for CETUS clinician accounts.

The secure recovery path: requires filesystem access to the SQLite DB (which is the
real trust boundary for this local-only app). Use it when a clinician is locked out.

Examples (point --db at the data folder next to the app you ran):
    python tools/admin_reset.py --db dist/data/cravingcrave.db list
    python tools/admin_reset.py --db dist/data/cravingcrave.db reset AlanH "NewPass123"
    python tools/admin_reset.py --db dist/data/cravingcrave.db create drnew "Dra. Nueva" "Pass123"

Resetting a password preserves all patient/session data (only the password hash
changes). Passwords are stored as PBKDF2-HMAC-SHA256, same as the app.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cravingcrave.domain.models import utc_now_iso  # noqa: E402
from cravingcrave.services.auth import hash_password, verify_password  # noqa: E402


def _connect(db: str) -> sqlite3.Connection:
    if not Path(db).exists():
        sys.exit(f"DB not found: {db}")
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def cmd_list(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, username, display_name, created_at FROM clinician").fetchall()
    if not rows:
        print("(no clinician accounts — the app will offer first-run account creation)")
        return
    print("Clinician accounts:")
    for r in rows:
        print(f"  id={r[0]}  username={r[1]!r}  name={r[2]!r}  created={r[3]}")


def cmd_reset(conn: sqlite3.Connection, username: str, password: str) -> None:
    row = conn.execute("SELECT id FROM clinician WHERE username = ?", (username,)).fetchone()
    if row is None:
        sys.exit(f"No clinician with username {username!r}. Use 'list' to see accounts.")
    new_hash = hash_password(password)
    conn.execute("UPDATE clinician SET password_hash = ? WHERE id = ?", (new_hash, row[0]))
    conn.commit()
    stored = conn.execute("SELECT password_hash FROM clinician WHERE id = ?", (row[0],)).fetchone()[0]
    assert verify_password(password, stored), "verification failed"
    print(f"Password reset for {username!r}. You can now log in with the new password.")


def cmd_create(conn: sqlite3.Connection, username: str, display_name: str, password: str) -> None:
    exists = conn.execute("SELECT 1 FROM clinician WHERE username = ?", (username,)).fetchone()
    if exists:
        sys.exit(f"Username {username!r} already exists. Use 'reset' instead.")
    conn.execute(
        "INSERT INTO clinician (username, display_name, password_hash, created_at) VALUES (?,?,?,?)",
        (username, display_name or username, hash_password(password), utc_now_iso()),
    )
    conn.commit()
    print(f"Created clinician {username!r}. You can now log in.")


def main() -> None:
    ap = argparse.ArgumentParser(description="CETUS offline admin recovery.")
    ap.add_argument("--db", default="data/cravingcrave.db", help="path to cravingcrave.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p_reset = sub.add_parser("reset")
    p_reset.add_argument("username")
    p_reset.add_argument("password")
    p_create = sub.add_parser("create")
    p_create.add_argument("username")
    p_create.add_argument("display_name")
    p_create.add_argument("password")
    args = ap.parse_args()

    conn = _connect(args.db)
    try:
        if args.cmd == "list":
            cmd_list(conn)
        elif args.cmd == "reset":
            cmd_reset(conn, args.username, args.password)
        elif args.cmd == "create":
            cmd_create(conn, args.username, args.display_name, args.password)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
