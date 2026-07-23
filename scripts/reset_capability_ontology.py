from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "embodied_ai_jobs_v4.db"


def reset(database_path: Path) -> None:
    if not database_path.exists():
        raise SystemExit(f"Database not found: {database_path}")

    backup_path = database_path.with_name(database_path.name + "-before-llm-rebuild")
    if backup_path.exists():
        raise SystemExit(f"Backup already exists; refusing to overwrite: {backup_path}")
    shutil.copy2(database_path, backup_path)
    print(f"Backup created: {backup_path}")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        counts_before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "capabilities",
                "capability_aliases",
                "job_capability_links",
                "capability_extraction_runs",
                "capability_mentions",
                "capability_candidates",
                "capability_category_candidates",
                "capability_normalization_reviews",
            )
        }
        for table in (
            "capability_normalization_reviews",
            "capability_mentions",
            "capability_candidates",
            "capability_category_candidates",
            "capability_extraction_runs",
            "job_capability_links",
            "capability_aliases",
            "capabilities",
        ):
            connection.execute(f"DELETE FROM {table}")
        connection.execute(
            "UPDATE career_units SET capability_requirements=NULL,updated_at=datetime('now')"
        )
        sequence_tables = (
            "capability_normalization_reviews",
            "capability_mentions",
            "capability_candidates",
            "capability_category_candidates",
            "capability_extraction_runs",
            "job_capability_links",
            "capability_aliases",
            "capabilities",
        )
        connection.executemany(
            "DELETE FROM sqlite_sequence WHERE name=?",
            [(table,) for table in sequence_tables],
        )
        connection.commit()
        print("Capability ontology reset completed.")
        for table, count in counts_before.items():
            print(f"  {table}: removed {count}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    reset(args.database.resolve())
