"""SQLite connection management.

Single-connection, main-thread-only (the app is not concurrent). Foreign keys
are enforced and writes are wrapped in transactions so an abrupt close — e.g. the
patient hitting PANIC — never leaves a half-written session.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Union

from . import migrations


class Database:
    def __init__(self, path: Union[str, Path] = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread stays True (default): all access is on the GUI thread.
        self.conn: sqlite3.Connection = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        migrations.apply_migrations(self.conn)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Atomic unit of work: commit on success, roll back on any exception."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def close(self) -> None:
        self.conn.close()


def open_database(path: Optional[Union[str, Path]] = None) -> Database:
    return Database(path if path is not None else ":memory:")
