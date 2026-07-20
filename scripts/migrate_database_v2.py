from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


LEGACY_TABLES = (
    "data_sources",
    "raw_jd_documents",
    "job_positions",
    "job_aliases",
    "skill_taxonomy",
    "skills",
    "job_skill_mapping",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_digest(connection: sqlite3.Connection, table: str) -> str:
    digest = hashlib.sha256()
    cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
    for row in cursor:
        # sqlite3.Row's default string includes an object identity, so normalize it
        # to a plain list before hashing values from two different connections.
        digest.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def copy_database(source: Path, target: Path) -> None:
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def seed_v2(connection: sqlite3.Connection, source_sha256: str, source_name: str) -> dict[str, int]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    connection.execute(
        """
        INSERT INTO ingestion_batches(
            batch_code, source_file, source_sha256, started_at, completed_at,
            input_count, accepted_count, status, config_json, report_json
        )
        SELECT 'legacy-baseline-001', ?, ?, MIN(created_at), MAX(created_at),
               COUNT(*), COUNT(*), 'completed',
               json_object('mode','legacy_baseline','preserve_values',1),
               json_object('note','Rows copied from the original database without value changes')
        FROM raw_jd_documents
        """,
        (source_name, source_sha256),
    )
    batch_id = connection.execute(
        "SELECT id FROM ingestion_batches WHERE batch_code='legacy-baseline-001'"
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO jd_batch_memberships(batch_id, jd_id, action, reason)
        SELECT ?, id, 'imported', 'legacy baseline row' FROM raw_jd_documents
        """,
        (batch_id,),
    )

    connection.execute(
        """
        INSERT INTO companies(normalized_name, display_name)
        SELECT lower(trim(company_name)), MIN(trim(company_name))
        FROM raw_jd_documents
        WHERE company_name IS NOT NULL AND trim(company_name) <> ''
        GROUP BY lower(trim(company_name))
        """
    )
    connection.execute(
        """
        INSERT INTO jd_company_links(jd_id, company_id, confidence, method)
        SELECT r.id, c.id, 1.0, 'legacy_exact'
        FROM raw_jd_documents r
        JOIN companies c ON c.normalized_name = lower(trim(r.company_name))
        """
    )

    connection.execute(
        """
        INSERT INTO job_categories(
            id, parent_id, category_code, category_name, category_level,
            sort_order, description, icon, created_at
        )
        SELECT id, parent_id, printf('JC-%04d', id), category_name,
               category_level, sort_order, description, icon, created_at
        FROM skill_taxonomy
        ORDER BY category_level, id
        """
    )
    connection.execute(
        """
        INSERT INTO job_category_memberships(job_id, category_id, is_primary, valid_from)
        SELECT j.id, c.id, 1, COALESCE(j.first_identified_at, j.created_at, ?)
        FROM job_positions j
        JOIN job_categories c
          ON c.category_level = 3 AND trim(c.category_name) = trim(j.job_name)
        """,
        (now,),
    )

    connection.execute(
        """
        INSERT INTO skill_categories(parent_id, category_code, category_name, category_level, description, sort_order)
        VALUES (NULL, 'SC-ROOT', '技能体系', 1, '具身智能岗位技能分类根节点', 0)
        """
    )
    root_id = connection.execute(
        "SELECT id FROM skill_categories WHERE category_code='SC-ROOT'"
    ).fetchone()[0]
    skill_type_labels = {
        "hard_skill": "专业技能",
        "soft_skill": "通用能力",
        "tool": "工具与平台",
        "domain_knowledge": "领域知识",
        "certification": "认证资质",
    }
    for order, (skill_type, label) in enumerate(skill_type_labels.items(), start=1):
        connection.execute(
            """
            INSERT INTO skill_categories(parent_id, category_code, category_name, category_level, description, sort_order)
            VALUES (?, ?, ?, 2, ?, ?)
            """,
            (root_id, f"SC-TYPE-{skill_type.upper()}", label, f"由旧库 skill_type={skill_type} 迁移", order),
        )
    connection.execute(
        """
        INSERT INTO skill_category_memberships(skill_id, category_id, is_primary, confidence, method)
        SELECT s.id, c.id, 1, 1.0, 'legacy_skill_type'
        FROM skills s
        JOIN skill_categories c ON c.category_code = 'SC-TYPE-' || upper(s.skill_type)
        """
    )

    snapshot_code = "baseline-v1"
    metrics = connection.execute(
        """
        SELECT json_object(
            'jd_count', (SELECT COUNT(*) FROM raw_jd_documents),
            'job_count', (SELECT COUNT(*) FROM job_positions),
            'skill_count', (SELECT COUNT(*) FROM skills),
            'job_skill_count', (SELECT COUNT(*) FROM v_job_skill_current)
        )
        """
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO graph_snapshots(
            snapshot_code, snapshot_name, snapshot_at, source_db_sha256,
            status, is_baseline, metrics_json
        ) VALUES (?, ?, ?, ?, 'ready', 1, ?)
        """,
        (snapshot_code, "原始数据库基线快照", now, source_sha256, metrics),
    )
    snapshot_id = connection.execute(
        "SELECT id FROM graph_snapshots WHERE snapshot_code=?", (snapshot_code,)
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO job_definition_versions(
            snapshot_id, job_id, version_no, job_name, core_responsibilities,
            typical_scenarios, career_path, seniority_levels, confidence_score,
            is_verified, valid_from
        )
        SELECT ?, id, version, job_name, core_responsibilities, typical_scenarios,
               career_path, seniority_levels, confidence_score, is_verified,
               COALESCE(first_identified_at, created_at, ?)
        FROM job_positions
        """,
        (snapshot_id, now),
    )
    connection.execute(
        """
        INSERT INTO skill_definition_versions(
            snapshot_id, skill_id, version_no, skill_name, skill_type,
            difficulty_level, description, demand_trend, demand_score, valid_from
        )
        SELECT ?, id, 1, skill_name, skill_type, difficulty_level, description,
               demand_trend, demand_score, COALESCE(first_appeared_at, created_at, ?)
        FROM skills
        """,
        (snapshot_id, now),
    )
    connection.execute(
        """
        INSERT INTO job_skill_evidence(
            mapping_id, jd_id, evidence_role, extraction_method,
            extraction_confidence, is_human_verified, created_at
        )
        SELECT m.id, CAST(j.value AS INTEGER), 'legacy_support', 'legacy_import',
               m.confidence, 0, COALESCE(m.created_at, ?)
        FROM job_skill_mapping m, json_each(m.source_jd_ids) j
        JOIN raw_jd_documents r ON r.id = CAST(j.value AS INTEGER)
        """,
        (now,),
    )
    connection.execute(
        """
        INSERT INTO graph_snapshot_job_skills(
            snapshot_id, mapping_id, job_id, skill_id, relation_version,
            importance, proficiency_required, weight, confidence, status,
            evidence_count, valid_from
        )
        SELECT ?, m.id, m.job_id, m.skill_id, m.version, m.importance,
               m.proficiency_required, m.weight, m.confidence, m.status,
               (SELECT COUNT(*) FROM job_skill_evidence e WHERE e.mapping_id=m.id),
               COALESCE(m.changed_at, m.created_at, ?)
        FROM v_job_skill_current m
        """,
        (snapshot_id, now),
    )

    connection.execute(
        """
        INSERT INTO schema_migrations(version, description, source_sha256)
        VALUES ('2.0.0', 'Add evidence, taxonomy, snapshot, review, and graph sync structures', ?)
        """,
        (source_sha256,),
    )

    names = (
        "ingestion_batches",
        "jd_batch_memberships",
        "companies",
        "jd_company_links",
        "job_categories",
        "job_category_memberships",
        "skill_categories",
        "skill_category_memberships",
        "graph_snapshots",
        "job_definition_versions",
        "skill_definition_versions",
        "job_skill_evidence",
        "graph_snapshot_job_skills",
    )
    return {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}


def migrate(source: Path, target: Path, migration_sql: Path, report_path: Path) -> dict:
    if target.exists():
        raise FileExistsError(f"Target already exists: {target}. Refusing to overwrite it.")
    if not source.exists():
        raise FileNotFoundError(source)

    source_hash = sha256_file(source)
    copy_database(source, target)

    try:
        with sqlite3.connect(source) as src:
            src.row_factory = sqlite3.Row
            before = {
                table: {
                    "count": src.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                    "digest": table_digest(src, table),
                }
                for table in LEGACY_TABLES
            }

        with sqlite3.connect(target) as dst:
            dst.execute("PRAGMA foreign_keys=ON")
            dst.executescript(migration_sql.read_text(encoding="utf-8"))
            with dst:
                seeded = seed_v2(dst, source_hash, source.name)

            after = {
                table: {
                    "count": dst.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                    "digest": table_digest(dst, table),
                }
                for table in LEGACY_TABLES
            }
            integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_errors = [tuple(row) for row in dst.execute("PRAGMA foreign_key_check")]

        unchanged = before == after
        report = {
            "source": str(source),
            "target": str(target),
            "source_sha256": source_hash,
            "target_sha256": sha256_file(target),
            "legacy_tables_unchanged": unchanged,
            "legacy_before": before,
            "legacy_after": after,
            "seeded_counts": seeded,
            "integrity_check": integrity,
            "foreign_key_errors": foreign_key_errors,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not unchanged or integrity != "ok" or foreign_key_errors:
            raise RuntimeError("Migration verification failed; see report")
        return report
    except Exception:
        # Keep the generated copy for forensic inspection. Never delete or overwrite
        # a database automatically when a verification step fails.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a non-destructive v2 copy of the embodied AI jobs database")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--migration", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = migrate(args.source.resolve(), args.target.resolve(), args.migration.resolve(), args.report.resolve())
    print(json.dumps({
        "target": report["target"],
        "legacy_tables_unchanged": report["legacy_tables_unchanged"],
        "integrity_check": report["integrity_check"],
        "foreign_key_error_count": len(report["foreign_key_errors"]),
        "seeded_counts": report["seeded_counts"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
