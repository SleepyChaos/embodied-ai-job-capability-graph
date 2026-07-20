from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from migrate_database_v2 import LEGACY_TABLES, table_digest


def verify(source: Path, target: Path) -> dict:
    result: dict = {"legacy_tables": {}, "checks": {}}
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        dst.execute("PRAGMA foreign_keys=ON")
        for table in LEGACY_TABLES:
            src_count = src.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            dst_count = dst.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            src_digest = table_digest(src, table)
            dst_digest = table_digest(dst, table)
            result["legacy_tables"][table] = {
                "source_count": src_count,
                "target_count": dst_count,
                "same_count": src_count == dst_count,
                "same_values": src_digest == dst_digest,
            }

        result["checks"] = {
            "integrity": dst.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_errors": [tuple(row) for row in dst.execute("PRAGMA foreign_key_check")],
            "schema_version": dst.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0],
            "baseline_snapshots": dst.execute("SELECT COUNT(*) FROM graph_snapshots WHERE is_baseline=1").fetchone()[0],
            "job_categories": dst.execute("SELECT COUNT(*) FROM job_categories").fetchone()[0],
            "job_memberships": dst.execute("SELECT COUNT(*) FROM job_category_memberships").fetchone()[0],
            "skill_memberships": dst.execute("SELECT COUNT(*) FROM skill_category_memberships").fetchone()[0],
            "evidence_rows": dst.execute("SELECT COUNT(*) FROM job_skill_evidence").fetchone()[0],
            "snapshot_edges": dst.execute("SELECT COUNT(*) FROM graph_snapshot_job_skills").fetchone()[0],
            "graph_nodes": dst.execute("SELECT COUNT(*) FROM v_graph_nodes").fetchone()[0],
            "graph_edges": dst.execute("SELECT COUNT(*) FROM v_graph_edges").fetchone()[0],
        }

    result["passed"] = (
        all(item["same_count"] and item["same_values"] for item in result["legacy_tables"].values())
        and result["checks"]["integrity"] == "ok"
        and not result["checks"]["foreign_key_errors"]
        and result["checks"]["schema_version"] == "2.0.0"
        and result["checks"]["baseline_snapshots"] == 1
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
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
