from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
        finally:
            connection.close()

    connect = read

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def health(self) -> dict:
        if not self.path.exists():
            return {"status": "unavailable", "reason": "database file missing"}
        try:
            with self.connect() as connection:
                integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
                version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            return {"status": "ok" if integrity == "ok" else "degraded", "schemaVersion": version}
        except sqlite3.Error as error:
            return {"status": "unavailable", "reason": str(error)}
