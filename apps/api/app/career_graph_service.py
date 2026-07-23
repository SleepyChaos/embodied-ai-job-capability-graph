from __future__ import annotations

from collections import defaultdict
from typing import Any

from .capability_graph_service import DIRECTION_COLORS
from .database import Database


class CareerGraphService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def overview(self, focus_job_id: int | None = None, sibling_limit: int = 12) -> dict[str, Any]:
        with self.database.read() as conn:
            linked_jobs = conn.execute(
                """
                SELECT cu.id,cu.job_title,cu.city,cu.company_id,cu.updated_at,
                       co.name AS company_name,
                       COUNT(DISTINCT c.id) AS capability_count
                FROM career_units cu
                JOIN job_capability_links l ON l.career_unit_id=cu.id
                JOIN capability_aliases a ON a.id=l.capability_alias_id
                JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                LEFT JOIN companies co ON co.id=cu.company_id
                GROUP BY cu.id
                ORDER BY cu.id
                """
            ).fetchall()
            linked_ids = {int(row["id"]) for row in linked_jobs}
            included_jobs = {int(row["id"]): row for row in linked_jobs}
            focus_company_id = None
            if focus_job_id is not None:
                focus = conn.execute(
                    """
                    SELECT cu.id,cu.job_title,cu.city,cu.company_id,cu.updated_at,
                           co.name AS company_name,
                           COUNT(DISTINCT c.id) AS capability_count
                    FROM career_units cu
                    LEFT JOIN companies co ON co.id=cu.company_id
                    LEFT JOIN job_capability_links l ON l.career_unit_id=cu.id
                    LEFT JOIN capability_aliases a ON a.id=l.capability_alias_id
                    LEFT JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                    WHERE cu.id=?
                    GROUP BY cu.id
                    """,
                    (focus_job_id,),
                ).fetchone()
                if focus is not None:
                    included_jobs[int(focus["id"])] = focus
                    focus_company_id = focus["company_id"]
            if focus_company_id is not None and sibling_limit:
                siblings = conn.execute(
                    """
                    SELECT cu.id,cu.job_title,cu.city,cu.company_id,cu.updated_at,
                           co.name AS company_name,
                           COUNT(DISTINCT c.id) AS capability_count
                    FROM career_units cu
                    LEFT JOIN companies co ON co.id=cu.company_id
                    LEFT JOIN job_capability_links l ON l.career_unit_id=cu.id
                    LEFT JOIN capability_aliases a ON a.id=l.capability_alias_id
                    LEFT JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                    WHERE cu.company_id=? AND cu.id<>?
                    GROUP BY cu.id
                    ORDER BY CASE WHEN COUNT(DISTINCT c.id)>0 THEN 0 ELSE 1 END,
                             cu.updated_at DESC,cu.id DESC
                    LIMIT ?
                    """,
                    (focus_company_id, focus_job_id, sibling_limit),
                ).fetchall()
                for row in siblings:
                    included_jobs[int(row["id"])] = row

            job_ids = sorted(included_jobs)
            placeholders = ",".join("?" for _ in job_ids)
            links = conn.execute(
                f"""
                SELECT l.career_unit_id,c.id AS capability_id,c.name AS capability_name,
                       c.description AS capability_description,
                       cc.name AS category_name,cd.name AS direction_name,cd.code AS direction_code,
                       MAX(l.confidence) AS confidence,
                       GROUP_CONCAT(DISTINCT a.alias_name) AS aliases,
                       COUNT(DISTINCT l.id) AS evidence_count
                FROM job_capability_links l
                JOIN capability_aliases a ON a.id=l.capability_alias_id
                JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                JOIN capability_categories cc ON cc.id=c.category_id
                JOIN capability_directions cd ON cd.id=cc.direction_id
                WHERE l.career_unit_id IN ({placeholders})
                GROUP BY l.career_unit_id,c.id
                ORDER BY l.career_unit_id,c.id
                """,
                job_ids,
            ).fetchall() if job_ids else []

            company_ids = sorted({
                int(row["company_id"]) for row in included_jobs.values()
                if row["company_id"] is not None
            })
            company_counts: dict[int, int] = {}
            if company_ids:
                company_placeholders = ",".join("?" for _ in company_ids)
                count_rows = conn.execute(
                    f"""
                    SELECT company_id,COUNT(*) AS job_count
                    FROM career_units
                    WHERE company_id IN ({company_placeholders})
                    GROUP BY company_id
                    """,
                    company_ids,
                ).fetchall()
                company_counts = {int(row["company_id"]): int(row["job_count"]) for row in count_rows}

            last_updated = conn.execute(
                """
                SELECT MAX(value) FROM (
                    SELECT MAX(updated_at) AS value FROM career_units
                    UNION ALL SELECT MAX(created_at) FROM job_capability_links
                )
                """
            ).fetchone()[0]

        capability_rows: dict[int, Any] = {}
        capability_job_ids: defaultdict[int, set[int]] = defaultdict(set)
        for row in links:
            capability_id = int(row["capability_id"])
            capability_rows[capability_id] = row
            capability_job_ids[capability_id].add(int(row["career_unit_id"]))

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visible_company_jobs: defaultdict[int, int] = defaultdict(int)
        for row in included_jobs.values():
            if row["company_id"] is not None:
                visible_company_jobs[int(row["company_id"])] += 1

        for company_id in company_ids:
            company_job = next(row for row in included_jobs.values() if int(row["company_id"]) == company_id)
            nodes.append({
                "id": f"company:{company_id}",
                "type": "career",
                "data": {
                    "databaseId": company_id,
                    "label": company_job["company_name"] or "未命名企业",
                    "kind": "company",
                    "jobCount": company_counts.get(company_id, 0),
                    "visibleJobCount": visible_company_jobs[company_id],
                    "color": "#e47a3e",
                },
            })

        for job_id, row in included_jobs.items():
            processed = job_id in linked_ids
            nodes.append({
                "id": f"job:{job_id}",
                "type": "career",
                "data": {
                    "databaseId": job_id,
                    "label": row["job_title"],
                    "kind": "job",
                    "city": row["city"],
                    "companyId": row["company_id"],
                    "companyName": row["company_name"],
                    "capabilityCount": int(row["capability_count"] or 0),
                    "processed": processed,
                    "focused": job_id == focus_job_id,
                    "color": "#155eef" if processed else "#94a3b8",
                },
            })
            if row["company_id"] is not None:
                edges.append({
                    "id": f"company-job:{row['company_id']}:{job_id}",
                    "source": f"job:{job_id}",
                    "target": f"company:{row['company_id']}",
                    "type": "POSTED_BY",
                    "data": {"weight": 1},
                })

        for capability_id, row in capability_rows.items():
            nodes.append({
                "id": f"capability:{capability_id}",
                "type": "capability",
                "data": {
                    "databaseId": capability_id,
                    "label": row["capability_name"],
                    "kind": "canonical",
                    "description": row["capability_description"],
                    "categoryName": row["category_name"],
                    "directionName": row["direction_name"],
                    "jobCount": len(capability_job_ids[capability_id]),
                    "color": DIRECTION_COLORS.get(str(row["direction_code"]), "#7155bd"),
                },
            })

        for row in links:
            job_id = int(row["career_unit_id"])
            capability_id = int(row["capability_id"])
            edges.append({
                "id": f"job-capability:{job_id}:{capability_id}",
                "source": f"job:{job_id}",
                "target": f"capability:{capability_id}",
                "type": "REQUIRES_CAPABILITY",
                "data": {
                    "confidence": float(row["confidence"]),
                    "aliases": row["aliases"] or "",
                    "evidenceCount": int(row["evidence_count"]),
                    "weight": 1,
                },
            })

        unprocessed_count = sum(
            1 for job_id in included_jobs if job_id not in linked_ids
        )
        warnings = []
        shared_capability_count = sum(
            1 for job_ids_for_capability in capability_job_ids.values()
            if len(job_ids_for_capability) > 1
        )
        if capability_rows and shared_capability_count == 0:
            warnings.append(
                "当前正式数据中每个能力总称暂只关联 1 条 JD；后续审批归并出共享总称后，"
                "跨 JD 的能力桥梁会自动形成。"
            )
        if focus_company_id is not None and company_counts.get(int(focus_company_id), 0) > sibling_limit:
            warnings.append(
                f"当前企业共 {company_counts[int(focus_company_id)]} 条 JD；画布仅增量展示 "
                f"{sibling_limit} 条同企业岗位，完整数量保留在详情中。"
            )
        return {
            "schemaVersion": "2",
            "graphType": "career",
            "snapshot": {
                "id": 0,
                "code": "live-career-attributes",
                "name": f"职业属性关联 · {len(included_jobs)} 条 JD",
                "at": last_updated,
                "status": "live",
                "baseline": False,
                "metrics": {
                    "jobCount": len(included_jobs),
                    "processedJobCount": len(linked_ids),
                    "companyCount": len(company_ids),
                    "capabilityCount": len(capability_rows),
                    "sharedCapabilityCount": shared_capability_count,
                    "contextJobCount": unprocessed_count,
                },
            },
            "nodes": nodes,
            "edges": edges,
            "combos": [],
            "meta": {
                "partial": focus_company_id is not None,
                "stale": False,
                "coverage": len(linked_ids) / max(1, len(included_jobs)),
                "warnings": warnings,
                "live": True,
                "focusJobId": focus_job_id,
            },
        }

    def neighborhood(self, node_key: str | None = None, neighbor_limit: int = 14) -> dict[str, Any]:
        with self.database.read() as conn:
            if not node_key:
                default_job = conn.execute(
                    """
                    SELECT cu.id
                    FROM career_units cu
                    JOIN job_capability_links l ON l.career_unit_id=cu.id
                    GROUP BY cu.id
                    ORDER BY COUNT(DISTINCT l.capability_alias_id) DESC,cu.id
                    LIMIT 1
                    """
                ).fetchone()
                if default_job is None:
                    return self.overview(None, 0)
                node_key = f"job:{int(default_job['id'])}"
            try:
                center_kind, raw_id = node_key.split(":", 1)
                center_id = int(raw_id)
            except (ValueError, AttributeError):
                center_kind, center_id = "job", 0
            if center_kind not in {"job", "company", "capability"}:
                center_kind = "job"

            job_ids: set[int] = set()
            company_ids: set[int] = set()
            capability_ids: set[int] = set()
            distance: dict[str, int] = {f"{center_kind}:{center_id}": 0}
            anchor: dict[str, str] = {}
            allowed_job_capability_edges: set[tuple[int, int]] = set()
            allowed_job_company_edges: set[tuple[int, int]] = set()

            if center_kind == "job":
                center_job = conn.execute(
                    """
                    SELECT cu.id,cu.company_id
                    FROM career_units cu
                    WHERE cu.id=?
                      AND EXISTS (
                          SELECT 1 FROM job_capability_links l
                          WHERE l.career_unit_id=cu.id
                      )
                    """,
                    (center_id,),
                ).fetchone()
                if center_job is None:
                    return self.neighborhood(None, neighbor_limit)
                job_ids.add(center_id)
                center_company_id = center_job["company_id"]
                capability_rows = conn.execute(
                    """
                    SELECT DISTINCT c.id
                    FROM job_capability_links l
                    JOIN capability_aliases a ON a.id=l.capability_alias_id
                    JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                    WHERE l.career_unit_id=?
                    ORDER BY c.id
                    """,
                    (center_id,),
                ).fetchall()
                for row in capability_rows:
                    capability_id = int(row["id"])
                    capability_ids.add(capability_id)
                    distance[f"capability:{capability_id}"] = 1
                    anchor[f"capability:{capability_id}"] = node_key
                    allowed_job_capability_edges.add((center_id, capability_id))
                if center_company_id is not None:
                    company_id = int(center_company_id)
                    company_ids.add(company_id)
                    distance[f"company:{company_id}"] = 1
                    anchor[f"company:{company_id}"] = node_key
                    allowed_job_company_edges.add((center_id, company_id))
                    sibling_rows = conn.execute(
                        """
                        SELECT cu.id
                        FROM career_units cu
                        JOIN job_capability_links l ON l.career_unit_id=cu.id
                        WHERE cu.company_id=? AND cu.id<>?
                        GROUP BY cu.id
                        ORDER BY cu.updated_at DESC,cu.id DESC
                        LIMIT ?
                        """,
                        (company_id, center_id, min(neighbor_limit, 8)),
                    ).fetchall()
                    for row in sibling_rows:
                        job_id = int(row["id"])
                        job_ids.add(job_id)
                        distance[f"job:{job_id}"] = 2
                        anchor[f"job:{job_id}"] = f"company:{company_id}"
                        allowed_job_company_edges.add((job_id, company_id))
                if capability_ids:
                    placeholders = ",".join("?" for _ in capability_ids)
                    shared_rows = conn.execute(
                        f"""
                        SELECT DISTINCT l.career_unit_id,c.id AS capability_id
                        FROM job_capability_links l
                        JOIN capability_aliases a ON a.id=l.capability_alias_id
                        JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                        WHERE c.id IN ({placeholders}) AND l.career_unit_id<>?
                        ORDER BY l.career_unit_id
                        LIMIT ?
                        """,
                        (*sorted(capability_ids), center_id, neighbor_limit),
                    ).fetchall()
                    for row in shared_rows:
                        job_id = int(row["career_unit_id"])
                        capability_id = int(row["capability_id"])
                        job_ids.add(job_id)
                        distance[f"job:{job_id}"] = 2
                        anchor[f"job:{job_id}"] = f"capability:{capability_id}"
                        allowed_job_capability_edges.add((job_id, capability_id))

            elif center_kind == "company":
                company = conn.execute(
                    """
                    SELECT co.id
                    FROM companies co
                    WHERE co.id=?
                      AND EXISTS (
                          SELECT 1
                          FROM career_units cu
                          JOIN job_capability_links l ON l.career_unit_id=cu.id
                          WHERE cu.company_id=co.id
                      )
                    """,
                    (center_id,),
                ).fetchone()
                if company is None:
                    return self.neighborhood(None, neighbor_limit)
                company_ids.add(center_id)
                job_rows = conn.execute(
                    """
                    SELECT cu.id
                    FROM career_units cu
                    JOIN job_capability_links l ON l.career_unit_id=cu.id
                    WHERE cu.company_id=?
                    GROUP BY cu.id
                    ORDER BY cu.updated_at DESC,cu.id DESC
                    LIMIT ?
                    """,
                    (center_id, neighbor_limit),
                ).fetchall()
                for row in job_rows:
                    job_id = int(row["id"])
                    job_ids.add(job_id)
                    distance[f"job:{job_id}"] = 1
                    anchor[f"job:{job_id}"] = node_key
                    allowed_job_company_edges.add((job_id, center_id))

            else:
                capability = conn.execute(
                    "SELECT id FROM capabilities WHERE id=? AND status='active'",
                    (center_id,),
                ).fetchone()
                if capability is None:
                    return self.neighborhood(None, neighbor_limit)
                capability_ids.add(center_id)
                job_rows = conn.execute(
                    """
                    SELECT DISTINCT l.career_unit_id,cu.company_id
                    FROM job_capability_links l
                    JOIN capability_aliases a ON a.id=l.capability_alias_id
                    JOIN career_units cu ON cu.id=l.career_unit_id
                    WHERE a.capability_id=?
                    ORDER BY l.career_unit_id
                    LIMIT ?
                    """,
                    (center_id, neighbor_limit),
                ).fetchall()
                for row in job_rows:
                    job_id = int(row["career_unit_id"])
                    job_ids.add(job_id)
                    distance[f"job:{job_id}"] = 1
                    anchor[f"job:{job_id}"] = node_key
                    allowed_job_capability_edges.add((job_id, center_id))
                    if row["company_id"] is not None:
                        company_id = int(row["company_id"])
                        company_ids.add(company_id)
                        company_key = f"company:{company_id}"
                        distance.setdefault(company_key, 2)
                        anchor.setdefault(company_key, f"job:{job_id}")
                        allowed_job_company_edges.add((job_id, company_id))

            job_rows_by_id: dict[int, Any] = {}
            if job_ids:
                placeholders = ",".join("?" for _ in job_ids)
                rows = conn.execute(
                    f"""
                    SELECT cu.id,cu.job_title,cu.city,cu.company_id,co.name AS company_name,
                           COUNT(DISTINCT c.id) AS capability_count
                    FROM career_units cu
                    LEFT JOIN companies co ON co.id=cu.company_id
                    LEFT JOIN job_capability_links l ON l.career_unit_id=cu.id
                    LEFT JOIN capability_aliases a ON a.id=l.capability_alias_id
                    LEFT JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                    WHERE cu.id IN ({placeholders})
                    GROUP BY cu.id
                    """,
                    sorted(job_ids),
                ).fetchall()
                job_rows_by_id = {int(row["id"]): row for row in rows}

            company_rows_by_id: dict[int, Any] = {}
            if company_ids:
                placeholders = ",".join("?" for _ in company_ids)
                rows = conn.execute(
                    f"""
                    SELECT co.id,co.name,COUNT(cu.id) AS job_count
                    FROM companies co
                    LEFT JOIN career_units cu ON cu.company_id=co.id
                    WHERE co.id IN ({placeholders})
                    GROUP BY co.id
                    """,
                    sorted(company_ids),
                ).fetchall()
                company_rows_by_id = {int(row["id"]): row for row in rows}

            capability_rows_by_id: dict[int, Any] = {}
            if capability_ids:
                placeholders = ",".join("?" for _ in capability_ids)
                rows = conn.execute(
                    f"""
                    SELECT c.id,c.name,c.description,cc.name AS category_name,
                           cd.name AS direction_name,cd.code AS direction_code,
                           COUNT(DISTINCT l.career_unit_id) AS job_count
                    FROM capabilities c
                    JOIN capability_categories cc ON cc.id=c.category_id
                    JOIN capability_directions cd ON cd.id=cc.direction_id
                    LEFT JOIN capability_aliases a ON a.capability_id=c.id
                    LEFT JOIN job_capability_links l ON l.capability_alias_id=a.id
                    WHERE c.id IN ({placeholders})
                    GROUP BY c.id
                    """,
                    sorted(capability_ids),
                ).fetchall()
                capability_rows_by_id = {int(row["id"]): row for row in rows}

            link_details: dict[tuple[int, int], Any] = {}
            if allowed_job_capability_edges:
                job_placeholders = ",".join("?" for _ in job_ids)
                capability_placeholders = ",".join("?" for _ in capability_ids)
                rows = conn.execute(
                    f"""
                    SELECT l.career_unit_id,a.capability_id,MAX(l.confidence) AS confidence,
                           GROUP_CONCAT(DISTINCT a.alias_name) AS aliases,
                           COUNT(DISTINCT l.id) AS evidence_count
                    FROM job_capability_links l
                    JOIN capability_aliases a ON a.id=l.capability_alias_id
                    WHERE l.career_unit_id IN ({job_placeholders})
                      AND a.capability_id IN ({capability_placeholders})
                    GROUP BY l.career_unit_id,a.capability_id
                    """,
                    (*sorted(job_ids), *sorted(capability_ids)),
                ).fetchall()
                link_details = {
                    (int(row["career_unit_id"]), int(row["capability_id"])): row
                    for row in rows
                }
            last_updated = conn.execute(
                """
                SELECT MAX(value) FROM (
                    SELECT MAX(updated_at) AS value FROM career_units
                    UNION ALL SELECT MAX(created_at) FROM job_capability_links
                )
                """
            ).fetchone()[0]

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for job_id, row in job_rows_by_id.items():
            node_id = f"job:{job_id}"
            nodes.append({
                "id": node_id,
                "type": "career",
                "data": {
                    "databaseId": job_id,
                    "label": row["job_title"],
                    "kind": "job",
                    "city": row["city"],
                    "companyId": row["company_id"],
                    "companyName": row["company_name"],
                    "capabilityCount": int(row["capability_count"] or 0),
                    "processed": int(row["capability_count"] or 0) > 0,
                    "focused": node_id == node_key,
                    "distance": distance.get(node_id, 2),
                    "anchorId": anchor.get(node_id),
                    "color": "#155eef" if int(row["capability_count"] or 0) > 0 else "#94a3b8",
                },
            })
        for company_id, row in company_rows_by_id.items():
            node_id = f"company:{company_id}"
            nodes.append({
                "id": node_id,
                "type": "career",
                "data": {
                    "databaseId": company_id,
                    "label": row["name"],
                    "kind": "company",
                    "jobCount": int(row["job_count"] or 0),
                    "focused": node_id == node_key,
                    "distance": distance.get(node_id, 2),
                    "anchorId": anchor.get(node_id),
                    "color": "#e47a3e",
                },
            })
        for capability_id, row in capability_rows_by_id.items():
            node_id = f"capability:{capability_id}"
            nodes.append({
                "id": node_id,
                "type": "capability",
                "data": {
                    "databaseId": capability_id,
                    "label": row["name"],
                    "kind": "canonical",
                    "description": row["description"],
                    "categoryName": row["category_name"],
                    "directionName": row["direction_name"],
                    "jobCount": int(row["job_count"] or 0),
                    "focused": node_id == node_key,
                    "distance": distance.get(node_id, 2),
                    "anchorId": anchor.get(node_id),
                    "color": DIRECTION_COLORS.get(str(row["direction_code"]), "#7155bd"),
                },
            })
        for job_id, company_id in allowed_job_company_edges:
            if job_id in job_rows_by_id and company_id in company_rows_by_id:
                edges.append({
                    "id": f"company-job:{company_id}:{job_id}",
                    "source": f"job:{job_id}",
                    "target": f"company:{company_id}",
                    "type": "POSTED_BY",
                    "data": {"weight": 1},
                })
        for job_id, capability_id in allowed_job_capability_edges:
            detail = link_details.get((job_id, capability_id))
            if detail and job_id in job_rows_by_id and capability_id in capability_rows_by_id:
                edges.append({
                    "id": f"job-capability:{job_id}:{capability_id}",
                    "source": f"job:{job_id}",
                    "target": f"capability:{capability_id}",
                    "type": "REQUIRES_CAPABILITY",
                    "data": {
                        "confidence": float(detail["confidence"]),
                        "aliases": detail["aliases"] or "",
                        "evidenceCount": int(detail["evidence_count"]),
                        "weight": 1,
                    },
                })
        center_label = next(
            (node["data"]["label"] for node in nodes if node["id"] == node_key),
            "职业关系",
        )
        return {
            "schemaVersion": "2",
            "graphType": "career",
            "snapshot": {
                "id": 0,
                "code": "live-career-neighborhood",
                "name": f"{center_label} · 关联邻域",
                "at": last_updated,
                "status": "live",
                "baseline": False,
                "metrics": {
                    "jobCount": len(job_rows_by_id),
                    "processedJobCount": sum(
                        1 for row in job_rows_by_id.values()
                        if int(row["capability_count"] or 0) > 0
                    ),
                    "companyCount": len(company_rows_by_id),
                    "capabilityCount": len(capability_rows_by_id),
                    "nodeCount": len(nodes),
                },
            },
            "nodes": nodes,
            "edges": edges,
            "combos": [],
            "meta": {
                "partial": True,
                "stale": False,
                "coverage": 1,
                "warnings": [],
                "live": True,
                "focusNodeId": node_key,
            },
        }

    def _all_database_directory(
        self,
        query: str = "",
        kind: str = "all",
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        normalized_kind = kind if kind in {"all", "job", "company", "capability"} else "all"
        directory_sql = """
            WITH directory AS (
                SELECT 'job' AS kind,0 AS kind_order,cu.id AS database_id,
                       cu.job_title AS label,COALESCE(co.name,'') AS secondary,
                       cu.company_id AS company_id,
                       COUNT(DISTINCT c.id) AS capability_count,
                       0 AS job_count,
                       CASE WHEN COUNT(DISTINCT c.id)>0 THEN 1 ELSE 0 END AS processed,
                       '' AS description,'' AS direction_name,'' AS category_name,
                       '' AS direction_code
                FROM career_units cu
                LEFT JOIN companies co ON co.id=cu.company_id
                LEFT JOIN job_capability_links l ON l.career_unit_id=cu.id
                LEFT JOIN capability_aliases a ON a.id=l.capability_alias_id
                LEFT JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                GROUP BY cu.id
                UNION ALL
                SELECT 'company',1,co.id,co.name,'',NULL,0,COUNT(cu.id),1,
                       COALESCE(co.description,''),'','',''
                FROM companies co
                LEFT JOIN career_units cu ON cu.company_id=co.id
                GROUP BY co.id
                UNION ALL
                SELECT 'capability',2,c.id,c.name,
                       cd.name || ' / ' || cc.name,NULL,0,
                       COUNT(DISTINCT l.career_unit_id),1,
                       COALESCE(c.description,''),cd.name,cc.name,cd.code
                FROM capabilities c
                JOIN capability_categories cc ON cc.id=c.category_id
                JOIN capability_directions cd ON cd.id=cc.direction_id
                LEFT JOIN capability_aliases a ON a.capability_id=c.id
                LEFT JOIN job_capability_links l ON l.capability_alias_id=a.id
                WHERE c.status='active'
                GROUP BY c.id
            )
        """
        filter_sql = """
            WHERE (?='all' OR kind=?)
              AND (?='' OR label LIKE ? OR secondary LIKE ?)
        """
        pattern = f"%{query.strip()}%"
        params: tuple[Any, ...] = (
            normalized_kind,
            normalized_kind,
            query.strip(),
            pattern,
            pattern,
        )
        with self.database.read() as conn:
            count_row = conn.execute(
                directory_sql + " SELECT COUNT(*) FROM directory " + filter_sql,
                params,
            ).fetchone()
            rows = conn.execute(
                directory_sql
                + " SELECT * FROM directory "
                + filter_sql
                + " ORDER BY kind_order,label,database_id LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
            totals = {
                "jobCount": int(conn.execute("SELECT COUNT(*) FROM career_units").fetchone()[0]),
                "companyCount": int(conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]),
                "capabilityCount": int(
                    conn.execute("SELECT COUNT(*) FROM capabilities WHERE status='active'").fetchone()[0]
                ),
            }
            last_updated = conn.execute(
                """
                SELECT MAX(value) FROM (
                    SELECT MAX(updated_at) AS value FROM career_units
                    UNION ALL SELECT MAX(updated_at) FROM companies
                    UNION ALL SELECT MAX(updated_at) FROM capabilities
                )
                """
            ).fetchone()[0]
        items: list[dict[str, Any]] = []
        for row in rows:
            row_kind = str(row["kind"])
            database_id = int(row["database_id"])
            node_id = (
                f"capability:{database_id}"
                if row_kind == "capability"
                else f"{row_kind}:{database_id}"
            )
            node_type = "capability" if row_kind == "capability" else "career"
            data_kind = "canonical" if row_kind == "capability" else row_kind
            color = (
                DIRECTION_COLORS.get(str(row["direction_code"]), "#7155bd")
                if row_kind == "capability"
                else "#e47a3e" if row_kind == "company"
                else "#155eef" if bool(row["processed"]) else "#94a3b8"
            )
            items.append({
                "id": node_id,
                "type": node_type,
                "data": {
                    "databaseId": database_id,
                    "label": row["label"],
                    "kind": data_kind,
                    "companyId": row["company_id"],
                    "companyName": row["secondary"] if row_kind == "job" else None,
                    "capabilityCount": int(row["capability_count"] or 0),
                    "jobCount": int(row["job_count"] or 0),
                    "processed": bool(row["processed"]),
                    "description": row["description"],
                    "directionName": row["direction_name"],
                    "categoryName": row["category_name"],
                    "color": color,
                },
            })
        total = int(count_row[0])
        return {
            "at": last_updated,
            "items": items,
            "metrics": totals,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "hasMore": page * page_size < total,
            "query": query,
            "kind": normalized_kind,
        }

    def directory(self) -> dict[str, Any]:
        payload = self.overview(None, 0)
        return {
            "at": payload["snapshot"]["at"],
            "items": payload["nodes"],
            "metrics": payload["snapshot"]["metrics"],
        }

    def job_detail(self, job_id: int) -> dict[str, Any] | None:
        with self.database.read() as conn:
            job = conn.execute(
                """
                SELECT cu.id,cu.job_title,cu.city,cu.salary,cu.experience,cu.education,
                       cu.jd_description,cu.url,cu.company_id,co.name AS company_name,
                       (SELECT COUNT(*) FROM career_units sibling WHERE sibling.company_id=cu.company_id) AS company_job_count
                FROM career_units cu
                LEFT JOIN companies co ON co.id=cu.company_id
                WHERE cu.id=?
                  AND EXISTS (
                      SELECT 1 FROM job_capability_links l
                      WHERE l.career_unit_id=cu.id
                  )
                """,
                (job_id,),
            ).fetchone()
            if job is None:
                return None
            capabilities = conn.execute(
                """
                SELECT c.id,c.name,c.description,cc.name AS category_name,
                       cd.name AS direction_name,MAX(l.confidence) AS confidence,
                       GROUP_CONCAT(DISTINCT a.alias_name) AS aliases,
                       GROUP_CONCAT(DISTINCT l.evidence_text) AS evidence
                FROM job_capability_links l
                JOIN capability_aliases a ON a.id=l.capability_alias_id
                JOIN capabilities c ON c.id=a.capability_id AND c.status='active'
                JOIN capability_categories cc ON cc.id=c.category_id
                JOIN capability_directions cd ON cd.id=cc.direction_id
                WHERE l.career_unit_id=?
                GROUP BY c.id
                ORDER BY cd.sort_order,cc.sort_order,c.name
                """,
                (job_id,),
            ).fetchall()
        return {
            "id": int(job["id"]),
            "title": job["job_title"],
            "city": job["city"],
            "salary": job["salary"],
            "experience": job["experience"],
            "education": job["education"],
            "description": job["jd_description"],
            "url": job["url"],
            "company": {
                "id": job["company_id"],
                "name": job["company_name"],
                "jobCount": int(job["company_job_count"] or 0),
            },
            "processed": bool(capabilities),
            "capabilities": [
                {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "description": row["description"],
                    "category": row["category_name"],
                    "direction": row["direction_name"],
                    "confidence": float(row["confidence"]),
                    "aliases": (row["aliases"] or "").split(","),
                    "evidence": (row["evidence"] or "").split(","),
                }
                for row in capabilities
            ],
        }
