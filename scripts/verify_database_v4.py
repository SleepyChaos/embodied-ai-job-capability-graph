from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from migrate_database_v2 import sha256_file, table_digest
from migrate_database_v3 import source_tables


OPERATIONAL_APPEND_TABLES = {
    "graph_snapshots",
    "job_capability_profiles",
    "job_similarities",
    "job_similarity_explanations",
    "job_similarity_runs",
}


def snapshot(connection: sqlite3.Connection, table: str) -> dict[str, object]:
    return {
        "count": connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
        "digest": table_digest(connection, table),
    }


def scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()):
    return connection.execute(sql, params).fetchone()[0]


def verify(source: Path, target: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "source": str(source),
        "target": str(target),
        "source_sha256": sha256_file(source),
        "target_sha256": sha256_file(target),
        "preserved_tables": {},
        "checks": {},
    }
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
    try:
        src.row_factory = sqlite3.Row
        dst.row_factory = sqlite3.Row
        tables = source_tables(src)
        for table in tables:
            before = snapshot(src, table)
            after = snapshot(dst, table)
            source_rows = {tuple(row) for row in src.execute(f'SELECT * FROM "{table}"')}
            target_rows = {tuple(row) for row in dst.execute(f'SELECT * FROM "{table}"')}
            result["preserved_tables"][table] = {
                "source_count": before["count"],
                "target_count": after["count"],
                "same_count": before["count"] == after["count"],
                "same_values": before["digest"] == after["digest"],
                "source_rows_preserved": source_rows.issubset(target_rows),
                "operational_append_allowed": table in OPERATIONAL_APPEND_TABLES,
            }
        checks = {
            "integrity": scalar(dst, "PRAGMA integrity_check"),
            "foreign_key_errors": [tuple(row) for row in dst.execute("PRAGMA foreign_key_check")],
            "schema_version": scalar(dst, "SELECT MAX(version) FROM schema_migrations"),
            "raw_jd_count": scalar(dst, "SELECT COUNT(*) FROM raw_jd_documents"),
            "posting_count": scalar(dst, "SELECT COUNT(*) FROM job_postings"),
            "posting_version_count": scalar(dst, "SELECT COUNT(*) FROM job_posting_versions"),
            "orphan_raw_jd_versions": scalar(
                dst,
                """
                SELECT COUNT(*) FROM raw_jd_documents r
                WHERE NOT EXISTS (SELECT 1 FROM job_posting_versions v WHERE v.raw_jd_id=r.id)
                """,
            ),
            "postings_without_current_version": scalar(
                dst,
                """
                SELECT COUNT(*) FROM job_postings p
                WHERE NOT EXISTS (
                    SELECT 1 FROM job_posting_versions v
                    WHERE v.posting_id=p.id AND v.is_current=1
                )
                """,
            ),
            "duplicate_postings": scalar(dst, "SELECT COUNT(*) FROM job_postings WHERE duplicate_of_id IS NOT NULL"),
            "embedding_models": scalar(dst, "SELECT COUNT(*) FROM embedding_models"),
            "configured_dimensions": scalar(
                dst,
                "SELECT dimensions FROM embedding_models WHERE model_code='bge-small-zh-v1.5'",
            ),
            "vector_runs": scalar(dst, "SELECT COUNT(*) FROM vectorization_runs"),
            "invalid_ready_embeddings": scalar(
                dst,
                """
                SELECT COUNT(*) FROM jd_embeddings
                WHERE status='ready' AND (vector_blob IS NULL OR vector_norm IS NULL OR dimensions <= 0)
                """,
            ),
        }
        result["checks"] = checks
    finally:
        src.close()
        dst.close()

    preserved = all(
        (item["same_count"] and item["same_values"])
        or (item["operational_append_allowed"] and item["source_rows_preserved"])
        for item in result["preserved_tables"].values()
    )
    checks = result["checks"]
    result["passed"] = (
        preserved
        and checks["integrity"] == "ok"
        and not checks["foreign_key_errors"]
        and checks["schema_version"] == "4.0.0"
        and checks["posting_version_count"] == checks["raw_jd_count"]
        and checks["orphan_raw_jd_versions"] == 0
        and checks["postings_without_current_version"] == 0
        and checks["embedding_models"] == 1
        and checks["configured_dimensions"] == 512
        and checks["invalid_ready_embeddings"] == 0
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify v4 vector matching database")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify(args.source.resolve(), args.target.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
