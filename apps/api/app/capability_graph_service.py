from __future__ import annotations

from collections import defaultdict
from typing import Any

from .database import Database


DIRECTION_COLORS = {
    "CD1": "#6f8195",
    "CD2": "#426bb8",
    "CD3": "#7155bd",
    "CD4": "#8a64a8",
    "CD5": "#e47a3e",
    "CD6": "#7f7f8b",
}


class CapabilityGraphService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def tree(self) -> dict[str, Any]:
        with self.database.read() as conn:
            directions = conn.execute(
                """
                SELECT id,code,name,description,sort_order
                FROM capability_directions
                ORDER BY sort_order,id
                """
            ).fetchall()
            categories = conn.execute(
                """
                SELECT id,direction_id,code,name,description,sort_order
                FROM capability_categories
                ORDER BY direction_id,sort_order,id
                """
            ).fetchall()
            capabilities = conn.execute(
                """
                SELECT c.id,c.category_id,c.name,c.description,c.sort_order,
                       COUNT(DISTINCT a.id) AS alias_count,
                       GROUP_CONCAT(DISTINCT a.alias_name) AS alias_names,
                       COUNT(DISTINCT l.career_unit_id) AS job_count
                FROM capabilities c
                LEFT JOIN capability_aliases a ON a.capability_id=c.id
                LEFT JOIN job_capability_links l ON l.capability_alias_id=a.id
                WHERE c.status='active'
                GROUP BY c.id
                ORDER BY c.category_id,c.sort_order,c.name,c.id
                """
            ).fetchall()
            pending_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM capability_candidates WHERE status='pending'"
                ).fetchone()[0]
            )
            last_updated = conn.execute(
                """
                SELECT MAX(value) FROM (
                    SELECT MAX(updated_at) AS value FROM capabilities
                    UNION ALL
                    SELECT MAX(created_at) AS value FROM capability_aliases
                    UNION ALL
                    SELECT MAX(created_at) AS value FROM job_capability_links
                )
                """
            ).fetchone()[0]

        category_capability_count: defaultdict[int, int] = defaultdict(int)
        category_alias_count: defaultdict[int, int] = defaultdict(int)
        category_job_ids: defaultdict[int, set[int]] = defaultdict(set)
        direction_capability_count: defaultdict[int, int] = defaultdict(int)
        direction_alias_count: defaultdict[int, int] = defaultdict(int)
        category_direction = {int(row["id"]): int(row["direction_id"]) for row in categories}

        with self.database.read() as conn:
            job_rows = conn.execute(
                """
                SELECT c.category_id,c.id AS capability_id,l.career_unit_id
                FROM capabilities c
                JOIN capability_aliases a ON a.capability_id=c.id
                JOIN job_capability_links l ON l.capability_alias_id=a.id
                WHERE c.status='active'
                """
            ).fetchall()
        for row in capabilities:
            category_id = int(row["category_id"])
            direction_id = category_direction[category_id]
            category_capability_count[category_id] += 1
            category_alias_count[category_id] += int(row["alias_count"])
            direction_capability_count[direction_id] += 1
            direction_alias_count[direction_id] += int(row["alias_count"])
        for row in job_rows:
            category_job_ids[int(row["category_id"])].add(int(row["career_unit_id"]))

        direction_job_ids: defaultdict[int, set[int]] = defaultdict(set)
        for category_id, job_ids in category_job_ids.items():
            direction_job_ids[category_direction[category_id]].update(job_ids)

        nodes: list[dict[str, Any]] = [
            {
                "id": "capability-root",
                "type": "capability",
                "data": {
                    "databaseId": 0,
                    "label": "能力图谱",
                    "level": 0,
                    "kind": "root",
                    "description": "六大能力方向、二级分类与正式能力总称的实时层级视图。",
                    "capabilityCount": len(capabilities),
                    "aliasCount": sum(int(row["alias_count"]) for row in capabilities),
                    "jobCount": len({job_id for values in category_job_ids.values() for job_id in values}),
                    "sortOrder": 0,
                    "color": "#26364d",
                },
            }
        ]
        edges: list[dict[str, Any]] = []

        for direction in directions:
            direction_id = int(direction["id"])
            node_id = f"direction:{direction_id}"
            color = DIRECTION_COLORS.get(str(direction["code"]), "#64748b")
            nodes.append(
                {
                    "id": node_id,
                    "type": "capability",
                    "data": {
                        "databaseId": direction_id,
                        "label": direction["name"],
                        "code": direction["code"],
                        "level": 1,
                        "kind": "direction",
                        "description": direction["description"],
                        "capabilityCount": direction_capability_count[direction_id],
                        "aliasCount": direction_alias_count[direction_id],
                        "jobCount": len(direction_job_ids[direction_id]),
                        "sortOrder": int(direction["sort_order"]),
                        "color": color,
                    },
                }
            )
            edges.append(
                {
                    "id": f"parent:root:{node_id}",
                    "source": "capability-root",
                    "target": node_id,
                    "type": "PARENT_OF",
                    "data": {"weight": 1},
                }
            )

        direction_by_id = {int(row["id"]): row for row in directions}
        category_by_id = {int(row["id"]): row for row in categories}
        for category in categories:
            category_id = int(category["id"])
            direction = direction_by_id[int(category["direction_id"])]
            node_id = f"category:{category_id}"
            nodes.append(
                {
                    "id": node_id,
                    "type": "capability",
                    "data": {
                        "databaseId": category_id,
                        "label": category["name"],
                        "code": category["code"],
                        "level": 2,
                        "kind": "category",
                        "description": category["description"],
                        "capabilityCount": category_capability_count[category_id],
                        "aliasCount": category_alias_count[category_id],
                        "jobCount": len(category_job_ids[category_id]),
                        "sortOrder": int(category["sort_order"]),
                        "directionId": int(direction["id"]),
                        "directionName": direction["name"],
                        "color": DIRECTION_COLORS.get(str(direction["code"]), "#64748b"),
                    },
                }
            )
            edges.append(
                {
                    "id": f"parent:direction:{direction['id']}:{node_id}",
                    "source": f"direction:{direction['id']}",
                    "target": node_id,
                    "type": "PARENT_OF",
                    "data": {"weight": 1},
                }
            )

        for capability in capabilities:
            capability_id = int(capability["id"])
            category = category_by_id[int(capability["category_id"])]
            direction = direction_by_id[int(category["direction_id"])]
            node_id = f"capability:{capability_id}"
            nodes.append(
                {
                    "id": node_id,
                    "type": "capability",
                    "data": {
                        "databaseId": capability_id,
                        "label": capability["name"],
                        "level": 3,
                        "kind": "canonical",
                        "description": capability["description"],
                        "capabilityCount": 1,
                        "aliasCount": int(capability["alias_count"]),
                        "jobCount": int(capability["job_count"]),
                        "searchText": capability["alias_names"] or "",
                        "sortOrder": int(capability["sort_order"]),
                        "categoryId": int(category["id"]),
                        "categoryName": category["name"],
                        "directionId": int(direction["id"]),
                        "directionName": direction["name"],
                        "color": DIRECTION_COLORS.get(str(direction["code"]), "#64748b"),
                    },
                }
            )
            edges.append(
                {
                    "id": f"parent:category:{category['id']}:{node_id}",
                    "source": f"category:{category['id']}",
                    "target": node_id,
                    "type": "PARENT_OF",
                    "data": {"weight": 1},
                }
            )

        linked_capability_count = sum(1 for row in capabilities if int(row["job_count"]) > 0)
        warnings = []
        if pending_count:
            warnings.append(f"另有 {pending_count} 条能力候选等待审批，审批后会自动进入图谱。")
        return {
            "schemaVersion": "2",
            "graphType": "capability",
            "snapshot": {
                "id": 0,
                "code": "live-capability",
                "name": f"实时能力本体 · {len(capabilities)} 个总称",
                "at": last_updated,
                "baseline": False,
                "status": "live",
                "metrics": {
                    "directionCount": len(directions),
                    "categoryCount": len(categories),
                    "capabilityCount": len(capabilities),
                    "pendingCount": pending_count,
                },
            },
            "nodes": nodes,
            "edges": edges,
            "combos": [],
            "meta": {
                "partial": False,
                "stale": False,
                "coverage": linked_capability_count / max(1, len(capabilities)),
                "warnings": warnings,
                "live": True,
            },
        }

    def detail(self, capability_id: int) -> dict[str, Any] | None:
        with self.database.read() as conn:
            capability = conn.execute(
                """
                SELECT c.id,c.name,c.description,c.category_id,
                       cc.code AS category_code,cc.name AS category_name,
                       cd.code AS direction_code,cd.name AS direction_name
                FROM capabilities c
                JOIN capability_categories cc ON cc.id=c.category_id
                JOIN capability_directions cd ON cd.id=cc.direction_id
                WHERE c.id=? AND c.status='active'
                """,
                (capability_id,),
            ).fetchone()
            if capability is None:
                return None
            aliases = conn.execute(
                """
                SELECT id,alias_name,alias_type,confidence
                FROM capability_aliases
                WHERE capability_id=?
                ORDER BY confidence DESC,alias_name,id
                """,
                (capability_id,),
            ).fetchall()
            jobs = conn.execute(
                """
                SELECT cu.id,cu.job_title,co.name AS company_name,
                       MAX(l.confidence) AS confidence,
                       MAX(l.evidence_text) AS evidence_text,
                       GROUP_CONCAT(DISTINCT a.alias_name) AS matched_aliases,
                       GROUP_CONCAT(DISTINCT l.extraction_method) AS extraction_methods
                FROM job_capability_links l
                JOIN capability_aliases a ON a.id=l.capability_alias_id
                JOIN career_units cu ON cu.id=l.career_unit_id
                LEFT JOIN companies co ON co.id=cu.company_id
                WHERE a.capability_id=?
                GROUP BY cu.id
                ORDER BY confidence DESC,cu.job_title,cu.id
                LIMIT 200
                """,
                (capability_id,),
            ).fetchall()
        return {
            "id": int(capability["id"]),
            "name": capability["name"],
            "description": capability["description"],
            "path": [
                {"code": capability["direction_code"], "name": capability["direction_name"]},
                {"code": capability["category_code"], "name": capability["category_name"]},
            ],
            "aliases": [
                {
                    "id": int(row["id"]),
                    "name": row["alias_name"],
                    "type": row["alias_type"],
                    "confidence": float(row["confidence"]),
                }
                for row in aliases
            ],
            "jobs": [
                {
                    "id": int(row["id"]),
                    "title": row["job_title"],
                    "company": row["company_name"],
                    "confidence": float(row["confidence"]),
                    "evidence": row["evidence_text"],
                    "matchedAliases": (row["matched_aliases"] or "").split(","),
                    "extractionMethods": (row["extraction_methods"] or "").split(","),
                }
                for row in jobs
            ],
        }
