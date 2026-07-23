from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "embodied_ai_jobs_v4.db"
MIGRATION = PROJECT_ROOT / "database" / "migrations" / "005_llm_capability_governance.sql"


def apply(database_path: Path) -> None:
    if not database_path.exists():
        raise SystemExit(f"Database not found: {database_path}")
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version='005'"
        ).fetchone()
        if row:
            print("Migration 005 is already applied.")
            return
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(capabilities)")
        }
        expected_tables = {
            "capability_extraction_runs",
            "capability_category_candidates",
            "capability_candidates",
            "capability_mentions",
            "capability_normalization_reviews",
        }
        present_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if {"status", "review_status", "source", "merged_into_id"} <= columns and expected_tables <= present_tables:
            connection.execute(
                """
                INSERT INTO schema_migrations(version,description,source_sha256)
                VALUES ('005','LLM能力抽取、语义归一化与审核治理',
                        'manual-005-llm-capability-governance')
                """
            )
            connection.commit()
            print("Recovered an interrupted migration and registered version 005.")
            return
    finally:
        connection.close()

    backup_path = database_path.with_name(database_path.name + "-before-005")
    if not backup_path.exists():
        shutil.copy2(database_path, backup_path)
        print(f"Backup created: {backup_path}")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(MIGRATION.read_text(encoding="utf-8"))
        connection.commit()
        print("Migration 005 applied successfully.")
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
