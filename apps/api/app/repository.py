from __future__ import annotations

import json
import sqlite3
from collections import deque
from typing import Any

from .database import Database


def _properties(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def _node(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "key": row["node_key"],
        "type": row["node_type"],
        "label": row["label"],
        "properties": _properties(row["properties_json"]),
    }


def _edge(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "key": row["edge_key"],
        "type": row["edge_type"],
        "source": row["source_key"],
        "target": row["target_key"],
        "properties": _properties(row["properties_json"]),
    }


class KnowledgeGraphRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def latest_snapshot(self, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT snapshot_code, snapshot_name, snapshot_at, status, is_baseline, metrics_json
            FROM graph_snapshots
            WHERE status='ready'
            ORDER BY snapshot_at DESC, id DESC LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise LookupError("No ready graph snapshot")
        return {
            "code": row["snapshot_code"],
            "name": row["snapshot_name"],
            "at": row["snapshot_at"],
            "status": row["status"],
            "baseline": bool(row["is_baseline"]),
            "metrics": _properties(row["metrics_json"]),
        }

    def list_snapshots(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT snapshot_code, snapshot_name, snapshot_at, status, is_baseline, metrics_json
                FROM graph_snapshots ORDER BY snapshot_at DESC, id DESC
                """
            ).fetchall()
        return [
            {
                "code": row["snapshot_code"],
                "name": row["snapshot_name"],
                "at": row["snapshot_at"],
                "status": row["status"],
                "baseline": bool(row["is_baseline"]),
                "metrics": _properties(row["metrics_json"]),
            }
            for row in rows
        ]

    def list_jobs(
        self,
        query: str | None,
        category: str | None,
        emerging: bool | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        values: list[Any] = []
        if query:
            clauses.append("(j.job_name LIKE ? OR j.job_name_en LIKE ? OR EXISTS (SELECT 1 FROM job_aliases a WHERE a.job_id=j.id AND a.alias_name LIKE ?))")
            pattern = f"%{query}%"
            values.extend([pattern, pattern, pattern])
        if category:
            clauses.append("(j.category_l1=? OR j.category_l2=?)")
            values.extend([category, category])
        if emerging is not None:
            clauses.append("j.is_emerging=?")
            values.append(1 if emerging else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM job_positions j {where}", values).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT j.id, j.job_name, j.job_code, j.category_l1, j.category_l2,
                       j.is_emerging,
                       COUNT(DISTINCT m.skill_id) AS skill_count,
                       COUNT(DISTINCT e.id) AS evidence_count
                FROM job_positions j
                LEFT JOIN v_job_skill_current m ON m.job_id=j.id
                LEFT JOIN job_skill_evidence e ON e.mapping_id=m.id
                {where}
                GROUP BY j.id
                ORDER BY skill_count DESC, j.job_name
                LIMIT ? OFFSET ?
                """,
                [*values, page_size, (page - 1) * page_size],
            ).fetchall()
        items = [
            {
                "id": row["id"],
                "key": f"job:{row['id']}",
                "name": row["job_name"],
                "code": row["job_code"],
                "categoryL1": row["category_l1"],
                "categoryL2": row["category_l2"],
                "emerging": bool(row["is_emerging"]),
                "skillCount": row["skill_count"],
                "evidenceCount": row["evidence_count"],
            }
            for row in rows
        ]
        return {"items": items, "page": {"page": page, "pageSize": page_size, "total": total}}

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM job_positions WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return None
            snapshot = self.latest_snapshot(connection)
            skill_rows = connection.execute(
                """
                SELECT m.id AS mapping_id, m.skill_id, s.skill_name, s.skill_type,
                       m.importance, m.proficiency_required, m.weight, m.confidence,
                       m.version, COUNT(e.id) AS evidence_count,
                       SUM(CASE WHEN e.is_human_verified=1 THEN 1 ELSE 0 END) AS verified_count
                FROM v_job_skill_current m
                JOIN skills s ON s.id=m.skill_id
                LEFT JOIN job_skill_evidence e ON e.mapping_id=m.id
                WHERE m.job_id=?
                GROUP BY m.id
                ORDER BY CASE m.importance WHEN 'required' THEN 0 WHEN 'preferred' THEN 1 ELSE 2 END,
                         m.weight DESC, s.skill_name
                """,
                (job_id,),
            ).fetchall()
            jd_count = connection.execute(
                "SELECT COUNT(*) FROM raw_jd_documents WHERE mapped_job_id=?", (job_id,)
            ).fetchone()[0]
        groups: dict[str, list[dict[str, Any]]] = {"required": [], "preferred": [], "optional": []}
        for skill in skill_rows:
            evidence_count = skill["evidence_count"]
            verified_count = skill["verified_count"] or 0
            groups.setdefault(skill["importance"], []).append(
                {
                    "mappingId": skill["mapping_id"],
                    "jobId": job_id,
                    "skillId": skill["skill_id"],
                    "skillKey": f"skill:{skill['skill_id']}",
                    "skillName": skill["skill_name"],
                    "skillType": skill["skill_type"],
                    "importance": skill["importance"],
                    "proficiency": skill["proficiency_required"],
                    "weight": skill["weight"],
                    "confidence": skill["confidence"],
                    "version": skill["version"],
                    "evidenceCount": evidence_count,
                    "evidenceStatus": "verified" if verified_count else ("unverified" if evidence_count else "missing"),
                }
            )
        return {
            "id": row["id"],
            "key": f"job:{row['id']}",
            "name": row["job_name"],
            "nameEn": row["job_name_en"],
            "code": row["job_code"],
            "categoryL1": row["category_l1"],
            "categoryL2": row["category_l2"],
            "emerging": bool(row["is_emerging"]),
            "responsibilities": row["core_responsibilities"],
            "scenarios": row["typical_scenarios"],
            "skillCount": sum(len(items) for items in groups.values()),
            "evidenceCount": sum(item["evidenceCount"] for items in groups.values() for item in items),
            "jdCount": jd_count,
            "snapshot": snapshot,
            "skillGroups": groups,
        }

    def list_skills(self, query: str | None, skill_type: str | None, page: int, page_size: int) -> dict[str, Any]:
        clauses: list[str] = []
        values: list[Any] = []
        if query:
            clauses.append("(s.skill_name LIKE ? OR s.skill_name_en LIKE ?)")
            values.extend([f"%{query}%", f"%{query}%"])
        if skill_type:
            clauses.append("s.skill_type=?")
            values.append(skill_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM skills s {where}", values).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT s.id, s.skill_name, s.skill_type, s.demand_trend, s.demand_score,
                       COUNT(DISTINCT m.job_id) AS job_count, COUNT(DISTINCT e.id) AS evidence_count
                FROM skills s
                LEFT JOIN v_job_skill_current m ON m.skill_id=s.id
                LEFT JOIN job_skill_evidence e ON e.mapping_id=m.id
                {where}
                GROUP BY s.id ORDER BY job_count DESC, s.skill_name
                LIMIT ? OFFSET ?
                """,
                [*values, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [
                {
                    "id": row["id"], "key": f"skill:{row['id']}", "name": row["skill_name"],
                    "type": row["skill_type"], "trend": row["demand_trend"],
                    "demandScore": row["demand_score"], "jobCount": row["job_count"],
                    "evidenceCount": row["evidence_count"],
                }
                for row in rows
            ],
            "page": {"page": page, "pageSize": page_size, "total": total},
        }

    def overview(self, aggregation: str, max_nodes: int, max_edges: int) -> dict[str, Any]:
        with self.database.connect() as connection:
            snapshot = self.latest_snapshot(connection)
            if aggregation == "category":
                node_rows = connection.execute(
                    """
                    SELECT * FROM v_graph_nodes
                    WHERE node_type='JobCategory' AND json_extract(properties_json,'$.level') <= 2
                    ORDER BY json_extract(properties_json,'$.level'), label
                    """
                ).fetchall()
                node_keys = {row["node_key"] for row in node_rows}
                edge_rows = [
                    row for row in connection.execute(
                        "SELECT * FROM v_graph_edges WHERE edge_type='HAS_CHILD_CATEGORY'"
                    ).fetchall()
                    if row["source_key"] in node_keys and row["target_key"] in node_keys
                ]
            elif aggregation == "job":
                node_rows = connection.execute(
                    "SELECT * FROM v_graph_nodes WHERE node_type IN ('JobCategory','Job') ORDER BY node_type,label"
                ).fetchall()
                node_keys = {row["node_key"] for row in node_rows}
                edge_rows = [
                    row for row in connection.execute(
                        "SELECT * FROM v_graph_edges WHERE edge_type IN ('HAS_CHILD_CATEGORY','CONTAINS_JOB')"
                    ).fetchall()
                    if row["source_key"] in node_keys and row["target_key"] in node_keys
                ]
            else:
                node_rows = connection.execute("SELECT * FROM v_graph_nodes ORDER BY node_type,label").fetchall()
                edge_rows = connection.execute("SELECT * FROM v_graph_edges ORDER BY edge_type,edge_key").fetchall()
        partial = len(node_rows) > max_nodes or len(edge_rows) > max_edges
        selected_nodes = node_rows[:max_nodes]
        selected_keys = {row["node_key"] for row in selected_nodes}
        selected_edges = [row for row in edge_rows if row["source_key"] in selected_keys and row["target_key"] in selected_keys][:max_edges]
        return {
            "snapshot": snapshot,
            "nodes": [_node(row) for row in selected_nodes],
            "edges": [_edge(row) for row in selected_edges],
            "meta": {
                "partial": partial,
                "stale": False,
                "nodeCount": len(selected_nodes),
                "edgeCount": len(selected_edges),
                "totalNodeCount": len(node_rows),
                "totalEdgeCount": len(edge_rows),
                "aggregation": aggregation,
                "warnings": ["结果已按响应预算截断"] if partial else [],
            },
        }

    def neighborhood(self, node_key: str, depth: int, max_nodes: int, max_edges: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            root = connection.execute("SELECT * FROM v_graph_nodes WHERE node_key=?", (node_key,)).fetchone()
            if root is None:
                return None
            snapshot = self.latest_snapshot(connection)
            all_nodes = {row["node_key"]: row for row in connection.execute("SELECT * FROM v_graph_nodes")}
            all_edges = connection.execute("SELECT * FROM v_graph_edges").fetchall()
        adjacency: dict[str, list[sqlite3.Row]] = {}
        for edge in all_edges:
            adjacency.setdefault(edge["source_key"], []).append(edge)
            adjacency.setdefault(edge["target_key"], []).append(edge)
        visited = {node_key}
        selected_edges: dict[str, sqlite3.Row] = {}
        queue: deque[tuple[str, int]] = deque([(node_key, 0)])
        while queue and len(visited) < max_nodes and len(selected_edges) < max_edges:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            candidates = adjacency.get(current, [])
            candidates = sorted(
                candidates,
                key=lambda item: (
                    0 if item["edge_type"] == "REQUIRES_SKILL" else 1,
                    -float(_properties(item["properties_json"]).get("weight") or 0),
                    item["edge_key"],
                ),
            )
            for edge in candidates:
                if len(selected_edges) >= max_edges:
                    break
                other = edge["target_key"] if edge["source_key"] == current else edge["source_key"]
                if other not in all_nodes:
                    continue
                selected_edges[edge["edge_key"]] = edge
                if other not in visited and len(visited) < max_nodes:
                    visited.add(other)
                    queue.append((other, current_depth + 1))
        ordered_keys = [node_key, *sorted(visited - {node_key})]
        return {
            "snapshot": snapshot,
            "nodes": [_node(all_nodes[key]) for key in ordered_keys],
            "edges": [_edge(edge) for edge in selected_edges.values() if edge["source_key"] in visited and edge["target_key"] in visited],
            "meta": {
                "partial": len(visited) >= max_nodes or len(selected_edges) >= max_edges,
                "stale": False,
                "nodeCount": len(visited),
                "edgeCount": len(selected_edges),
                "root": node_key,
                "depth": depth,
                "aggregation": "neighborhood",
                "warnings": [],
            },
        }

    def list_evidence(
        self,
        mapping_id: int | None,
        job_id: int | None,
        skill_id: int | None,
        verified: bool | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (("mapping_id", mapping_id), ("job_id", job_id), ("skill_id", skill_id)):
            if value is not None:
                clauses.append(f"{column}=?")
                values.append(value)
        if verified is not None:
            clauses.append("is_human_verified=?")
            values.append(1 if verified else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM v_job_skill_evidence_detail {where}", values).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM v_job_skill_evidence_detail {where}
                ORDER BY is_human_verified DESC, fetched_at DESC, evidence_id
                LIMIT ? OFFSET ?
                """,
                [*values, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [self._evidence_item(row) for row in rows],
            "page": {"page": page, "pageSize": page_size, "total": total},
        }

    def get_evidence(self, evidence_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM v_job_skill_evidence_detail WHERE evidence_id=?", (evidence_id,)
            ).fetchone()
            if row is None:
                return None
            raw = connection.execute("SELECT raw_content FROM raw_jd_documents WHERE id=?", (row["jd_id"],)).fetchone()[0]
        item = self._evidence_item(row)
        item.update({"rawContent": raw, "contextBefore": None, "contextAfter": None})
        return item

    @staticmethod
    def _evidence_item(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["evidence_id"],
            "mappingId": row["mapping_id"],
            "jobId": row["job_id"],
            "jobName": row["job_name"],
            "skillId": row["skill_id"],
            "skillName": row["skill_name"],
            "jdId": row["jd_id"],
            "role": row["evidence_role"],
            "excerpt": row["evidence_text"],
            "source": row["source_name"] or "未知来源",
            "company": row["company_name"],
            "rawTitle": row["raw_title"],
            "url": row["fetch_url"],
            "fetchedAt": row["fetched_at"],
            "publishedAt": row["published_at"],
            "confidence": row["extraction_confidence"],
            "verified": bool(row["is_human_verified"]),
            "extractionMethod": row["extraction_method"],
        }
