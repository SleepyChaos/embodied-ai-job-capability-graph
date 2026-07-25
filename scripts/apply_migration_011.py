from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "data" / "embodied_ai_jobs_v4.db"
MIGRATION_PATH = ROOT / "database" / "migrations" / "011_job_pipeline_status.sql"


def main() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(DATABASE_PATH) as connection:
        exists = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version='011'"
        ).fetchone()
        if exists:
            print("migration 011 already applied")
            return
        connection.executescript(sql)
    print("migration 011 applied")


if __name__ == "__main__":
    main()
