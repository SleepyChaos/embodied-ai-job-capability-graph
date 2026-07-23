from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "embodied_ai_jobs_v4.db"
MIGRATION = PROJECT_ROOT / "database" / "migrations" / "006_capability_taxonomy_descriptions.sql"


def apply(database_path: Path) -> None:
    if not database_path.exists():
        raise SystemExit(f"Database not found: {database_path}")
    connection = sqlite3.connect(database_path)
    try:
        if connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version='006'"
        ).fetchone():
            print("Migration 006 is already applied.")
            return
        connection.executescript(MIGRATION.read_text(encoding="utf-8"))
        connection.commit()
        print("Migration 006 applied successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    apply(args.database.resolve())
