from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.career_clustering_service import CareerClusteringService  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.llm_capability_service import DeepSeekClient  # noqa: E402


def eligible_ids(database: Database, limit: int) -> list[int]:
    with database.read() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT cu.id
            FROM career_units cu
            JOIN job_capability_links l ON l.career_unit_id=cu.id
            JOIN capability_aliases a ON a.id=l.capability_alias_id
            JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
            WHERE NOT EXISTS (
                SELECT 1 FROM career_cluster_memberships m
                WHERE m.career_unit_id=cu.id
            )
              AND NOT EXISTS (
                SELECT 1 FROM career_cluster_candidates cand
                WHERE cand.career_unit_id=cu.id AND cand.status='pending'
            )
            ORDER BY cu.id LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [int(row["id"]) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the production LLM career clustering pipeline."
    )
    parser.add_argument("career_unit_ids", nargs="*", type=int)
    parser.add_argument("--eligible", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    database = Database(settings.database_path)
    service = CareerClusteringService(
        database,
        DeepSeekClient(
            settings.llm_api_key,
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_timeout_seconds,
        ),
    )
    career_unit_ids = list(args.career_unit_ids)
    if args.eligible:
        career_unit_ids.extend(eligible_ids(database, args.eligible))
    career_unit_ids = list(dict.fromkeys(career_unit_ids))
    if not career_unit_ids:
        raise SystemExit("请提供职业单元ID或使用 --eligible")

    results = []
    for career_unit_id in career_unit_ids:
        try:
            result = service.cluster_career_unit(career_unit_id, force=args.force)
            run = result["run"]
            item = {
                "careerUnitId": career_unit_id,
                "runId": run["id"],
                "status": run["status"],
                "attemptCount": run["attempt_count"],
                "decision": result.get("decision"),
                "resolvedClusterId": result.get("resolvedClusterId"),
            }
        except Exception as error:
            item = {
                "careerUnitId": career_unit_id,
                "status": "failed",
                "error": str(error),
            }
        results.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    print(json.dumps({"items": results}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
