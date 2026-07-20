from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SENSITIVE_TABLES = (
    "job_match_decisions",
    "job_match_candidates",
    "capability_candidates",
    "vectorization_runs",
    "career_embeddings",
    "jd_embeddings",
    "jd_capability_mentions",
    "job_posting_versions",
    "job_postings",
    "job_skill_evidence",
    "jd_batch_memberships",
    "jd_company_links",
    "raw_jd_documents",
    "companies",
    "data_sources",
    "ingestion_batches",
    "manual_review_tasks",
    "change_events",
)


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def create_demo(source: Path, target: Path) -> dict[str, int | str]:
    if target.exists():
        raise FileExistsError(f"target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
        target_connection.execute("PRAGMA foreign_keys=OFF")
        for table in SENSITIVE_TABLES:
            if table_exists(target_connection, table):
                target_connection.execute(f'DELETE FROM "{table}"')
        if table_exists(target_connection, "embedding_models"):
            target_connection.execute(
                "UPDATE embedding_models SET model_sha256=NULL,status='configured'"
            )
        if table_exists(target_connection, "graph_snapshots"):
            target_connection.execute(
                "UPDATE graph_snapshots SET source_db_sha256='sanitized-demo'"
            )
        target_connection.commit()
        target_connection.execute("VACUUM")
        target_connection.execute("PRAGMA foreign_keys=ON")
        integrity = target_connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = target_connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError(f"demo validation failed: integrity={integrity}, fk={foreign_keys[:5]}")
        return {
            "integrity": integrity,
            "capabilityNodes": target_connection.execute("SELECT COUNT(*) FROM capability_nodes").fetchone()[0],
            "jobs": target_connection.execute("SELECT COUNT(*) FROM job_positions").fetchone()[0],
            "rawJds": target_connection.execute("SELECT COUNT(*) FROM raw_jd_documents").fetchone()[0],
            "profileRows": target_connection.execute("SELECT COUNT(*) FROM job_capability_profiles").fetchone()[0],
            "similarities": target_connection.execute("SELECT COUNT(*) FROM job_similarities").fetchone()[0],
        }
    finally:
        source_connection.close()
        target_connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a sanitized v4 demo database")
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "embodied_ai_jobs_v4.db")
    parser.add_argument("--target", type=Path, default=PROJECT_ROOT / "database" / "demo_v4.db")
    args = parser.parse_args()
    result = create_demo(args.source.resolve(), args.target.resolve())
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
