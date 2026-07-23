from __future__ import annotations

from collections import defaultdict
from typing import Any

from .capability_graph_service import DIRECTION_COLORS
from .database import Database


class CareerSpectrumService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def overview(self) -> dict[str, Any]:
        with self.database.read() as conn:
            career_directions = conn.execute(
                """
                SELECT id,code,name,sort_order
                FROM career_directions
                ORDER BY sort_order,id
                """
            ).fetchall()
            sub_directions = conn.execute(
                """
                SELECT id,direction_id,code,name,sort_order
                FROM career_sub_directions
                ORDER BY direction_id,sort_order,id
                """
            ).fetchall()
            jobs = conn.execute(
                """
                SELECT cu.id,cu.job_title,cu.city,cu.salary,cu.experience,cu.education,
                       cu.company_id,co.name AS company_name,
                       COUNT(DISTINCT c.id) AS capability_count,
                       AVG(l.confidence) AS average_confidence
                FROM career_units cu
                JOIN job_capability_links l ON l.career_unit_id=cu.id
                JOIN capability_aliases a ON a.id=l.capability_alias_id
                JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                LEFT JOIN companies co ON co.id=cu.company_id
                GROUP BY cu.id
                ORDER BY cu.id
                """
            ).fetchall()
            classification_rows = conn.execute(
                """
                SELECT l.career_unit_id,cd.sort_order AS direction_order,
                       cc.sort_order AS category_order,
                       COUNT(DISTINCT c.id) AS capability_count,
                       AVG(l.confidence) AS average_confidence
                FROM job_capability_links l
                JOIN capability_aliases a ON a.id=l.capability_alias_id
                JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                JOIN capability_categories cc ON cc.id=c.category_id
                JOIN capability_directions cd ON cd.id=cc.direction_id
                GROUP BY l.career_unit_id,cd.id,cc.id
                ORDER BY l.career_unit_id,cd.sort_order,cc.sort_order
                """
            ).fetchall()
            last_updated = conn.execute(
                """
                SELECT MAX(value) FROM (
                    SELECT MAX(updated_at) AS value FROM career_units
                    UNION ALL SELECT MAX(created_at) FROM job_capability_links
                    UNION ALL SELECT MAX(updated_at) FROM capabilities
                )
                """
            ).fetchone()[0]

        career_direction_by_order = {
            int(row["sort_order"]): row for row in career_directions
        }
        sub_direction_by_order = {
            (int(row["direction_id"]), int(row["sort_order"])): row
            for row in sub_directions
        }
        rows_by_job: defaultdict[int, list[Any]] = defaultdict(list)
        for row in classification_rows:
            rows_by_job[int(row["career_unit_id"])].append(row)

        direction_counts: defaultdict[int, int] = defaultdict(int)
        items: list[dict[str, Any]] = []
        for job in jobs:
            job_id = int(job["id"])
            category_rows = rows_by_job[job_id]
            direction_scores: defaultdict[int, dict[str, float]] = defaultdict(
                lambda: {"count": 0, "confidence": 0}
            )
            for row in category_rows:
                order = int(row["direction_order"])
                direction_scores[order]["count"] += int(row["capability_count"])
                direction_scores[order]["confidence"] += float(row["average_confidence"] or 0)
            dominant_direction_order = max(
                direction_scores,
                key=lambda order: (
                    direction_scores[order]["count"],
                    direction_scores[order]["confidence"],
                    -order,
                ),
            )
            dominant_categories = [
                row for row in category_rows
                if int(row["direction_order"]) == dominant_direction_order
            ]
            dominant_category = max(
                dominant_categories,
                key=lambda row: (
                    int(row["capability_count"]),
                    float(row["average_confidence"] or 0),
                    -int(row["category_order"]),
                ),
            )
            career_direction = career_direction_by_order[dominant_direction_order]
            sub_direction = sub_direction_by_order[
                (int(career_direction["id"]), int(dominant_category["category_order"]))
            ]
            direction_counts[dominant_direction_order] += 1
            items.append({
                "id": job_id,
                "title": job["job_title"],
                "companyId": job["company_id"],
                "company": job["company_name"],
                "city": job["city"],
                "salary": job["salary"],
                "experience": job["experience"],
                "education": job["education"],
                "capabilityCount": int(job["capability_count"]),
                "averageConfidence": float(job["average_confidence"] or 0),
                "directionId": int(career_direction["id"]),
                "directionCode": career_direction["code"],
                "directionName": career_direction["name"],
                "directionOrder": dominant_direction_order,
                "subDirectionId": int(sub_direction["id"]),
                "subDirectionCode": sub_direction["code"],
                "subDirectionName": sub_direction["name"],
                "color": DIRECTION_COLORS.get(
                    f"CD{dominant_direction_order}", "#64748b"
                ),
                "classificationSource": "approved_capability_majority",
            })

        directions = []
        for direction in career_directions:
            order = int(direction["sort_order"])
            directions.append({
                "id": int(direction["id"]),
                "code": direction["code"],
                "name": direction["name"],
                "sortOrder": order,
                "count": direction_counts[order],
                "color": DIRECTION_COLORS.get(f"CD{order}", "#64748b"),
            })
        return {
            "snapshot": {
                "name": f"职业色系谱 · {len(items)} 条正式 JD",
                "at": last_updated,
                "metrics": {
                    "jobCount": len(items),
                    "directionCount": len(directions),
                    "companyCount": len({
                        item["companyId"] for item in items
                        if item["companyId"] is not None
                    }),
                },
            },
            "directions": directions,
            "jobs": items,
            "meta": {
                "live": True,
                "classificationSource": "approved_capability_majority",
                "warnings": [],
            },
        }
