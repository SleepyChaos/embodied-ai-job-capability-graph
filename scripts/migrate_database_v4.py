from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from migrate_database_v2 import copy_database, sha256_file
from migrate_database_v3 import snapshot_tables, source_tables


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(
        ch for ch in value.strip().casefold()
        if ch.isalnum() or ch in {"+", "#"} or "\u4e00" <= ch <= "\u9fff"
    )


def identity_for(row: sqlite3.Row) -> tuple[str, str]:
    if row["fetch_url"]:
        digest = hashlib.sha256(
            f"{row['source_id'] or 'none'}|{row['fetch_url'].strip()}".encode("utf-8")
        ).hexdigest()[:24]
        return f"url:{digest}", "source_url"
    return f"legacy:{row['id']}", "legacy_id"


def backfill_postings(connection: sqlite3.Connection, now: str) -> dict[str, int]:
    companies: dict[str, int] = {}
    for row in connection.execute("SELECT id, normalized_name, display_name FROM companies"):
        companies[normalize_text(row["normalized_name"])] = int(row["id"])
        companies[normalize_text(row["display_name"])] = int(row["id"])

    rows = connection.execute(
        """
        SELECT id, source_id, raw_title, content_hash, fetch_url, company_name,
               city, fetched_at, published_at, freshness_label
        FROM raw_jd_documents
        ORDER BY COALESCE(fetched_at, published_at, created_at), id
        """
    ).fetchall()
    grouped: defaultdict[tuple[int | None, str], list[sqlite3.Row]] = defaultdict(list)
    methods: dict[tuple[int | None, str], str] = {}
    for row in rows:
        external_id, method = identity_for(row)
        key = (row["source_id"], external_id)
        grouped[key].append(row)
        methods[key] = method

    posting_ids: dict[tuple[int | None, str], int] = {}
    for key, versions in grouped.items():
        source_id, external_id = key
        first = versions[0]
        last = versions[-1]
        company_id = companies.get(normalize_text(last["company_name"]))
        status = "open" if str(last["freshness_label"] or "").casefold() not in {"closed", "expired", "已关闭", "已过期"} else "closed"
        cursor = connection.execute(
            """
            INSERT INTO job_postings(
                source_id, company_id, external_job_id, canonical_url,
                current_raw_jd_id, posting_status, identity_method,
                first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                source_id,
                company_id,
                external_id,
                last["fetch_url"],
                last["id"],
                status,
                methods[key],
                first["fetched_at"] or first["published_at"],
                last["fetched_at"] or last["published_at"],
                now,
                now,
            ),
        )
        posting_id = int(cursor.lastrowid)
        posting_ids[key] = posting_id
        previous_hash: str | None = None
        for index, version in enumerate(versions, start=1):
            if index == 1:
                change_type = "initial"
            elif version["content_hash"] == previous_hash:
                change_type = "unchanged"
            else:
                change_type = "content_changed"
            connection.execute(
                """
                INSERT INTO job_posting_versions(
                    posting_id, raw_jd_id, version_no, content_hash,
                    change_type, is_current, observed_at, created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    posting_id,
                    version["id"],
                    index,
                    version["content_hash"],
                    change_type,
                    1 if index == len(versions) else 0,
                    version["fetched_at"] or version["published_at"],
                    now,
                ),
            )
            previous_hash = version["content_hash"]

    duplicate_groups: defaultdict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for row in connection.execute(
        """
        SELECT p.id, r.content_hash, r.company_name, r.raw_title, r.city
        FROM job_postings p
        JOIN raw_jd_documents r ON r.id=p.current_raw_jd_id
        ORDER BY p.id
        """
    ):
        duplicate_groups[
            (
                row["content_hash"],
                normalize_text(row["company_name"]),
                normalize_text(row["raw_title"]),
                normalize_text(row["city"]),
            )
        ].append(int(row["id"]))

    duplicate_count = 0
    for ids in duplicate_groups.values():
        if len(ids) < 2:
            continue
        canonical = ids[0]
        for duplicate in ids[1:]:
            connection.execute(
                "UPDATE job_postings SET duplicate_of_id=?, updated_at=? WHERE id=?",
                (canonical, now, duplicate),
            )
            duplicate_count += 1

    return {
        "posting_count": len(grouped),
        "version_count": len(rows),
        "duplicate_posting_count": duplicate_count,
    }


def migrate(source: Path, target: Path, migration_sql: Path, report_path: Path) -> dict[str, object]:
    if target.exists():
        raise FileExistsError(f"Target already exists: {target}. Refusing to overwrite it.")
    if not source.exists():
        raise FileNotFoundError(source)

    source_hash = sha256_file(source)
    copy_database(source, target)
    now = utc_now()

    src = sqlite3.connect(source)
    try:
        src.row_factory = sqlite3.Row
        preserved_tables = source_tables(src)
        before = snapshot_tables(src, preserved_tables)
    finally:
        src.close()

    dst = sqlite3.connect(target)
    try:
        dst.row_factory = sqlite3.Row
        dst.execute("PRAGMA foreign_keys=ON")
        dst.executescript(migration_sql.read_text(encoding="utf-8"))
        with dst:
            dst.execute(
                """
                INSERT INTO embedding_models(
                    model_code, provider, model_name, model_revision,
                    dimensions, distance_metric, normalized, status
                ) VALUES ('bge-small-zh-v1.5','sentence-transformers',
                          'BAAI/bge-small-zh-v1.5','main',512,'cosine',1,'configured')
                """
            )
            posting_metrics = backfill_postings(dst, now)
            dst.execute(
                """
                INSERT INTO schema_migrations(version, description, source_sha256)
                VALUES ('4.0.0','Add posting identity, vectorization and reviewed career matching pipeline',?)
                """,
                (source_hash,),
            )
        after = snapshot_tables(dst, preserved_tables)
        counts = {
            table: dst.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in (
                "job_postings",
                "job_posting_versions",
                "embedding_models",
                "vectorization_runs",
                "jd_capability_mentions",
                "jd_embeddings",
                "career_embeddings",
                "job_match_candidates",
                "job_match_decisions",
                "capability_candidates",
                "job_similarity_components",
            )
        }
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = [tuple(row) for row in dst.execute("PRAGMA foreign_key_check")]
    finally:
        dst.close()

    unchanged = before == after
    report: dict[str, object] = {
        "source": str(source),
        "target": str(target),
        "source_sha256": source_hash,
        "target_sha256": sha256_file(target),
        "preserved_tables_unchanged": unchanged,
        "preserved_table_count": len(preserved_tables),
        "preserved_before": before,
        "preserved_after": after,
        "posting_backfill": posting_metrics,
        "v4_counts": counts,
        "integrity_check": integrity,
        "foreign_key_errors": foreign_key_errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not unchanged or integrity != "ok" or foreign_key_errors:
        raise RuntimeError("v4 migration verification failed; see report")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create non-destructive v4 vector-matching database")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = migrate(
        args.source.resolve(),
        args.target.resolve(),
        args.migration.resolve(),
        args.report.resolve(),
    )
    print(json.dumps({
        "target": report["target"],
        "preserved_tables_unchanged": report["preserved_tables_unchanged"],
        "posting_backfill": report["posting_backfill"],
        "v4_counts": report["v4_counts"],
        "integrity_check": report["integrity_check"],
        "foreign_key_error_count": len(report["foreign_key_errors"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
