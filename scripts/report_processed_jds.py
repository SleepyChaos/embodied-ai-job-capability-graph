from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "data" / "embodied_ai_jobs_v4.db"


def main():
    conn = sqlite3.connect(DATABASE_PATH)
    cap_runs = conn.execute(
        """
        SELECT r.id, r.career_unit_id, r.status, r.attempt_count, r.raw_response_json, cu.job_title
        FROM capability_extraction_runs r
        JOIN career_units cu ON cu.id = r.career_unit_id
        WHERE r.status IN ('completed', 'completed_with_review')
        ORDER BY r.id DESC LIMIT 5
        """
    ).fetchall()

    print(f"=== 已完成最新 DeepSeek-v4-pro 流程提取的岗位记录 ({len(cap_runs)} 条) ===\n")

    report_list = []
    for run_id, job_id, status, attempts, raw_json, job_title in cap_runs:
        car_run = conn.execute(
            """
            SELECT status, raw_response_json FROM career_clustering_runs
            WHERE career_unit_id=? AND status IN ('completed', 'completed_with_review')
            ORDER BY id DESC LIMIT 1
            """,
            (job_id,),
        ).fetchone()

        caps_info = []
        mentions = conn.execute(
            """
            SELECT surface_name, proposed_canonical_name, extraction_confidence, classification_confidence
            FROM capability_mentions
            WHERE career_unit_id=?
            """,
            (job_id,),
        ).fetchall()

        for m in mentions:
            caps_info.append({
                "surfaceName": m[0],
                "proposedName": m[1],
                "extractionConfidence": m[2],
                "classificationConfidence": m[3],
            })

        cluster_info = {}
        if car_run and car_run[1]:
            car_data = json.loads(car_run[1])
            cluster_info = {
                "clusterName": car_data.get("cluster_name"),
                "namingDiagnosis": car_data.get("naming_diagnosis"),
                "direction": car_data.get("direction"),
                "subDirection": car_data.get("sub_direction"),
                "profileConfidence": car_data.get("profile_confidence"),
                "classificationConfidence": car_data.get("classification_confidence"),
            }

        report_list.append({
            "jobId": job_id,
            "jobTitle": job_title,
            "capabilityStatus": status,
            "attemptCount": attempts,
            "capabilityCount": len(caps_info),
            "capabilities": caps_info,
            "clusterResult": cluster_info,
        })

    print(json.dumps(report_list, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
