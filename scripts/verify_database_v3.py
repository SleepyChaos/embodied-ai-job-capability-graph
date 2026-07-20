from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from migrate_database_v2 import sha256_file, table_digest
from migrate_database_v3 import source_tables


def table_snapshot(connection: sqlite3.Connection, table: str) -> dict[str, object]:
    return {
        "count": connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
        "digest": table_digest(connection, table),
    }


def scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> int | float | str | None:
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
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.row_factory = sqlite3.Row
        dst.row_factory = sqlite3.Row
        dst.execute("PRAGMA foreign_keys=ON")

        preserved = source_tables(src)
        for table in preserved:
            source_snapshot = table_snapshot(src, table)
            target_snapshot = table_snapshot(dst, table)
            result["preserved_tables"][table] = {
                "source_count": source_snapshot["count"],
                "target_count": target_snapshot["count"],
                "same_count": source_snapshot["count"] == target_snapshot["count"],
                "same_values": source_snapshot["digest"] == target_snapshot["digest"],
            }

        hierarchy_count = scalar(dst, "SELECT COUNT(*) FROM capability_nodes")
        reachable_count = scalar(
            dst,
            """
            WITH RECURSIVE reachable(id) AS (
                SELECT id FROM capability_nodes WHERE parent_id IS NULL
                UNION ALL
                SELECT c.id FROM capability_nodes c JOIN reachable r ON c.parent_id=r.id
            )
            SELECT COUNT(DISTINCT id) FROM reachable
            """,
        )
        ambiguous_capability_aliases = [
            dict(row)
            for row in dst.execute(
                """
                SELECT normalized_alias, COUNT(DISTINCT capability_id) AS capability_count
                FROM capability_aliases
                GROUP BY normalized_alias
                HAVING COUNT(DISTINCT capability_id) > 1
                ORDER BY capability_count DESC, normalized_alias
                """
            )
        ]
        mapping_type_counts = {
            row[0]: row[1]
            for row in dst.execute(
                "SELECT mapping_type,COUNT(*) FROM skill_capability_mappings GROUP BY mapping_type"
            )
        }
        checks = {
            "integrity": scalar(dst, "PRAGMA integrity_check"),
            "foreign_key_errors": [tuple(row) for row in dst.execute("PRAGMA foreign_key_check")],
            "schema_version": scalar(dst, "SELECT MAX(version) FROM schema_migrations"),
            "ontology_versions": scalar(dst, "SELECT COUNT(*) FROM ontology_versions"),
            "current_ontology_versions": scalar(dst, "SELECT COUNT(*) FROM ontology_versions WHERE is_current=1"),
            "capability_nodes": hierarchy_count,
            "capability_root_count": scalar(dst, "SELECT COUNT(*) FROM capability_nodes WHERE level=0"),
            "capability_l1_count": scalar(dst, "SELECT COUNT(*) FROM capability_nodes WHERE level=1"),
            "capability_l2_count": scalar(dst, "SELECT COUNT(*) FROM capability_nodes WHERE level=2"),
            "capability_l3_count": scalar(dst, "SELECT COUNT(*) FROM capability_nodes WHERE level=3"),
            "capability_variant_count": scalar(dst, "SELECT COUNT(*) FROM capability_nodes WHERE node_kind='variant'"),
            "variant_relation_count": scalar(dst, "SELECT COUNT(*) FROM capability_relations WHERE relation_type='VARIANT_OF'"),
            "reachable_capability_nodes": reachable_count,
            "unreachable_capability_nodes": int(hierarchy_count or 0) - int(reachable_count or 0),
            "bad_parent_levels": scalar(
                dst,
                """
                SELECT COUNT(*)
                FROM capability_nodes c
                JOIN capability_nodes p ON p.id=c.parent_id
                WHERE p.level <> c.level-1 OR p.ontology_version_id <> c.ontology_version_id
                """,
            ),
            "ambiguous_capability_aliases": ambiguous_capability_aliases,
            "legacy_skill_count": scalar(dst, "SELECT COUNT(*) FROM skills"),
            "primary_skill_mapping_count": scalar(
                dst, "SELECT COUNT(*) FROM skill_capability_mappings WHERE is_primary=1"
            ),
            "unmapped_legacy_skills": scalar(
                dst,
                """
                SELECT COUNT(*) FROM skills s
                WHERE NOT EXISTS (
                    SELECT 1 FROM skill_capability_mappings m
                    WHERE m.skill_id=s.id AND m.is_primary=1
                )
                """,
            ),
            "mapping_type_counts": mapping_type_counts,
            "job_profile_count": scalar(dst, "SELECT COUNT(*) FROM job_capability_profiles"),
            "profiled_job_count": scalar(dst, "SELECT COUNT(DISTINCT job_id) FROM job_capability_profiles"),
            "unprofiled_job_count": scalar(
                dst,
                """
                SELECT COUNT(*) FROM job_positions j
                WHERE NOT EXISTS (
                    SELECT 1 FROM job_capability_profiles p WHERE p.job_id=j.id
                )
                """,
            ),
            "invalid_profile_values": scalar(
                dst,
                """
                SELECT COUNT(*) FROM job_capability_profiles
                WHERE weight NOT BETWEEN 0 AND 1
                   OR confidence NOT BETWEEN 0 AND 1
                   OR evidence_count < 0
                """,
            ),
            "similarity_runs": scalar(dst, "SELECT COUNT(*) FROM job_similarity_runs"),
            "similarity_edges": scalar(dst, "SELECT COUNT(*) FROM job_similarities"),
            "similarity_explanations": scalar(dst, "SELECT COUNT(*) FROM job_similarity_explanations"),
            "invalid_similarity_values": scalar(
                dst,
                """
                SELECT COUNT(*) FROM job_similarities
                WHERE job_a_id >= job_b_id
                   OR score_total NOT BETWEEN 0 AND 1
                   OR capability_cosine NOT BETWEEN 0 AND 1
                   OR core_jaccard NOT BETWEEN 0 AND 1
                   OR hierarchy_score NOT BETWEEN 0 AND 1
                   OR coverage_a NOT BETWEEN 0 AND 1
                   OR coverage_b NOT BETWEEN 0 AND 1
                """,
            ),
            "pending_similarity_edges": scalar(
                dst, "SELECT COUNT(*) FROM job_similarities WHERE review_status='pending'"
            ),
            "graph_v3_nodes": scalar(dst, "SELECT COUNT(*) FROM v_graph_v3_nodes"),
            "graph_v3_edges": scalar(dst, "SELECT COUNT(*) FROM v_graph_v3_edges"),
        }
        result["checks"] = checks

    preserved_ok = all(
        item["same_count"] and item["same_values"]
        for item in result["preserved_tables"].values()
    )
    checks = result["checks"]
    result["passed"] = (
        preserved_ok
        and checks["integrity"] == "ok"
        and not checks["foreign_key_errors"]
        and checks["schema_version"] == "3.0.0"
        and checks["ontology_versions"] == 1
        and checks["current_ontology_versions"] == 1
        and checks["capability_root_count"] == 1
        and checks["capability_l1_count"] == 6
        and checks["capability_variant_count"] == 4
        and checks["variant_relation_count"] == 4
        and checks["unreachable_capability_nodes"] == 0
        and checks["bad_parent_levels"] == 0
        and not checks["ambiguous_capability_aliases"]
        and checks["primary_skill_mapping_count"] == checks["legacy_skill_count"]
        and checks["unmapped_legacy_skills"] == 0
        and checks["invalid_profile_values"] == 0
        and checks["similarity_runs"] == 1
        and checks["invalid_similarity_values"] == 0
        and checks["pending_similarity_edges"] == checks["similarity_edges"]
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the non-destructive v3 graph database migration")
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
