from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .database import Database
from .vectorization import compose_embedding_text, normalize_label, text_hash


DOMAIN_COLORS = {
    "战略与管理": "#c2706a",
    "研究、设计与算法": "#d4925a",
    "工程开发与实现": "#c9a94e",
    "测试、生产与供应链": "#6a9e6e",
    "商业化、服务与支持": "#5e88b0",
    "职能支撑平台": "#7b6ea8",
}

CAPABILITY_L1_COLORS = {
    "战略与经营管理能力": "#c2706a",
    "研究、设计与算法能力": "#d4925a",
    "工程开发与实现能力": "#c9a94e",
    "测试、生产与供应链能力": "#6a9e6e",
    "商业化、服务与支持能力": "#5e88b0",
    "职能支撑能力": "#7b6ea8",
}


def _json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class V4Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _snapshot(connection: sqlite3.Connection) -> tuple[int, dict[str, Any]]:
        row = connection.execute(
            """
            SELECT id,snapshot_code,snapshot_name,snapshot_at,status,metrics_json
            FROM graph_snapshots WHERE status='ready'
            ORDER BY snapshot_at DESC,id DESC LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise LookupError("No ready graph snapshot")
        return int(row["id"]), {
            "id": int(row["id"]), "code": row["snapshot_code"], "name": row["snapshot_name"],
            "at": row["snapshot_at"], "status": row["status"], "metrics": _json(row["metrics_json"], {}),
        }

    def capability_graph(self, root_id: int | None = None, depth: int = 3) -> dict[str, Any]:
        with self.database.read() as connection:
            snapshot_id, snapshot = self._snapshot(connection)
            rows = connection.execute(
                """
                SELECT c.*,
                       (SELECT COUNT(*) FROM capability_aliases a WHERE a.capability_id=c.id AND a.review_status<>'rejected') alias_count,
                       (SELECT COUNT(DISTINCT p.job_id) FROM job_capability_profiles p WHERE p.snapshot_id=? AND p.capability_id=c.id) job_count
                FROM capability_nodes c WHERE c.status='active'
                ORDER BY c.level,c.sort_order,c.capability_name
                """, (snapshot_id,),
            ).fetchall()
            relation_rows = connection.execute(
                "SELECT * FROM capability_relations WHERE review_status<>'rejected'"
            ).fetchall()
        by_id = {int(row["id"]): row for row in rows}
        # Resolve L1 branch color for each node
        l1_color_map: dict[int, str] = {}
        for row in rows:
            if int(row["level"]) == 1:
                l1_color_map[int(row["id"])] = CAPABILITY_L1_COLORS.get(row["capability_name"], "#7b8a99")
        branch_color: dict[int, str] = {}
        for row in rows:
            nid = int(row["id"])
            if int(row["level"]) == 0:
                branch_color[nid] = "#4b5c6e"
            elif int(row["level"]) == 1:
                branch_color[nid] = l1_color_map.get(nid, "#7b8a99")
            else:
                ancestor = nid
                while ancestor and by_id.get(ancestor) is not None and int(by_id[ancestor]["level"]) > 1:
                    ancestor = int(by_id[ancestor]["parent_id"]) if by_id[ancestor]["parent_id"] else None
                branch_color[nid] = l1_color_map.get(ancestor, "#7b8a99") if ancestor else "#7b8a99"
        included: set[int]
        if root_id is None:
            included = {int(row["id"]) for row in rows if int(row["level"]) <= depth}
        elif root_id not in by_id:
            raise LookupError("capability not found")
        else:
            included = {root_id}
            frontier = {root_id}
            for _ in range(depth):
                frontier = {int(row["id"]) for row in rows if row["parent_id"] in frontier}
                included.update(frontier)

        nodes = []
        edges = []
        for row in rows:
            node_id = int(row["id"])
            if node_id not in included:
                continue
            nodes.append({
                "id": f"capability:{node_id}", "type": "capability",
                "data": {
                    "databaseId": node_id, "label": row["capability_name"], "code": row["capability_code"],
                    "level": int(row["level"]), "kind": row["node_kind"], "description": row["description"],
                    "aliasCount": int(row["alias_count"]), "jobCount": int(row["job_count"]),
                    "confidence": float(row["confidence"]), "reviewStatus": row["review_status"],
                    "color": branch_color.get(node_id, "#7b8a99"),
                },
            })
            if row["parent_id"] is not None and int(row["parent_id"]) in included:
                edges.append({
                    "id": f"capability-parent:{row['parent_id']}:{node_id}", "source": f"capability:{row['parent_id']}",
                    "target": f"capability:{node_id}", "type": "PARENT_OF", "data": {"weight": 1.0},
                })
        for relation in relation_rows:
            source = int(relation["source_capability_id"])
            target = int(relation["target_capability_id"])
            if source in included and target in included:
                edges.append({
                    "id": f"capability-relation:{relation['id']}", "source": f"capability:{source}",
                    "target": f"capability:{target}", "type": relation["relation_type"],
                    "data": {"weight": float(relation["weight"]), "confidence": float(relation["confidence"])},
                })
        coverage = int(snapshot["metrics"].get("profiledJobCount", 0)) / 106
        return {
            "schemaVersion": "2", "graphType": "capability", "snapshot": snapshot,
            "nodes": nodes, "edges": edges, "combos": [],
            "meta": {
                "partial": len(included) < len(rows), "stale": False, "coverage": min(1.0, coverage),
                "warnings": [] if coverage >= 0.8 else ["当前能力画像仅覆盖 30/106 个标准职业；未覆盖职业仍保留在职业目录中。"],
            },
        }

    def capability_detail(self, capability_id: int) -> dict[str, Any] | None:
        with self.database.read() as connection:
            row = connection.execute("SELECT * FROM capability_nodes WHERE id=?", (capability_id,)).fetchone()
            if row is None:
                return None
            aliases = [dict(item) for item in connection.execute(
                "SELECT id,alias_name,alias_type,confidence,review_status FROM capability_aliases WHERE capability_id=? ORDER BY confidence DESC,alias_name",
                (capability_id,),
            )]
            path = []
            cursor = row
            while cursor is not None:
                path.append({"id": int(cursor["id"]), "name": cursor["capability_name"], "level": int(cursor["level"])})
                cursor = connection.execute("SELECT * FROM capability_nodes WHERE id=?", (cursor["parent_id"],)).fetchone() if cursor["parent_id"] else None
        return {
            "id": capability_id, "name": row["capability_name"], "code": row["capability_code"],
            "level": int(row["level"]), "kind": row["node_kind"], "description": row["description"],
            "path": list(reversed(path)), "aliases": aliases, "confidence": float(row["confidence"]),
            "reviewStatus": row["review_status"],
        }

    def capability_relations(self, capability_id: int) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                """
                SELECT r.*,s.capability_name source_name,t.capability_name target_name
                FROM capability_relations r JOIN capability_nodes s ON s.id=r.source_capability_id
                JOIN capability_nodes t ON t.id=r.target_capability_id
                WHERE r.source_capability_id=? OR r.target_capability_id=? ORDER BY r.weight DESC
                """, (capability_id, capability_id),
            ).fetchall()
        return [{
            "id": int(row["id"]), "sourceId": int(row["source_capability_id"]), "sourceName": row["source_name"],
            "targetId": int(row["target_capability_id"]), "targetName": row["target_name"],
            "type": row["relation_type"], "weight": float(row["weight"]), "confidence": float(row["confidence"]),
        } for row in rows]

    def capability_jobs(self, capability_id: int) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            snapshot_id, _ = self._snapshot(connection)
            rows = connection.execute(
                """
                SELECT j.id,j.job_name,j.category_l1,j.category_l2,p.weight,p.jd_count,p.evidence_count
                FROM job_capability_profiles p JOIN job_positions j ON j.id=p.job_id
                WHERE p.snapshot_id=? AND p.capability_id=? ORDER BY p.weight DESC,j.job_name LIMIT 100
                """, (snapshot_id, capability_id),
            ).fetchall()
        return [{"id": int(r["id"]), "name": r["job_name"], "categoryL1": r["category_l1"], "categoryL2": r["category_l2"], "weight": float(r["weight"]), "jdCount": int(r["jd_count"]), "evidenceCount": int(r["evidence_count"])} for r in rows]

    def search_capabilities(self, query: str, limit: int) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        with self.database.read() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT c.id,c.capability_name,c.level,c.node_kind,c.parent_id
                FROM capability_nodes c LEFT JOIN capability_aliases a ON a.capability_id=c.id
                WHERE c.status='active' AND (c.capability_name LIKE ? OR a.alias_name LIKE ?)
                ORDER BY c.level,c.sort_order,c.capability_name LIMIT ?
                """, (pattern, pattern, limit),
            ).fetchall()
        return [{"id": int(r["id"]), "key": f"capability:{r['id']}", "name": r["capability_name"], "level": int(r["level"]), "kind": r["node_kind"], "parentId": r["parent_id"]} for r in rows]

    def career_graph(self, top_k: int = 4, threshold: float = 0.25) -> dict[str, Any]:
        with self.database.read() as connection:
            snapshot_id, snapshot = self._snapshot(connection)
            jobs = connection.execute(
                """
                SELECT j.*,COUNT(DISTINCT p.capability_id) capability_count,
                       COUNT(DISTINCT r.id) jd_count
                FROM job_positions j LEFT JOIN job_capability_profiles p ON p.job_id=j.id AND p.snapshot_id=?
                LEFT JOIN raw_jd_documents r ON r.mapped_job_id=j.id
                GROUP BY j.id ORDER BY j.category_l1,j.category_l2,j.job_name
                """, (snapshot_id,),
            ).fetchall()
            run = connection.execute(
                "SELECT id,algorithm_version,warning FROM job_similarity_runs WHERE snapshot_id=? AND status='succeeded' ORDER BY id DESC LIMIT 1",
                (snapshot_id,),
            ).fetchone()
            similarities = connection.execute(
                "SELECT * FROM job_similarities WHERE run_id=? AND score_total>=? ORDER BY score_total DESC",
                (int(run["id"]), threshold),
            ).fetchall() if run else []
        combos: list[dict[str, Any]] = []
        seen_l1: set[str] = set()
        seen_l2: set[tuple[str, str]] = set()
        nodes: list[dict[str, Any]] = []
        for row in jobs:
            l1 = row["category_l1"]
            l2 = row["category_l2"] or "其他"
            l1_id = f"domain:{hashlib.sha1(l1.encode()).hexdigest()[:10]}"
            l2_id = f"category:{hashlib.sha1((l1+'|'+l2).encode()).hexdigest()[:10]}"
            if l1 not in seen_l1:
                seen_l1.add(l1)
                combos.append({"id": l1_id, "type": "domain", "data": {"label": l1, "color": DOMAIN_COLORS.get(l1, "#475569")}})
            if (l1, l2) not in seen_l2:
                seen_l2.add((l1, l2))
                combos.append({"id": l2_id, "type": "category", "parentId": l1_id, "data": {"label": l2, "color": DOMAIN_COLORS.get(l1, "#475569")}})
            nodes.append({
                "id": f"job:{row['id']}", "type": "career", "comboId": l2_id,
                "data": {"databaseId": int(row["id"]), "label": row["job_name"], "categoryL1": l1,
                         "categoryL2": l2, "emerging": bool(row["is_emerging"]),
                         "capabilityCount": int(row["capability_count"]), "jdCount": int(row["jd_count"]),
                         "color": DOMAIN_COLORS.get(l1, "#475569")},
            })
        degree: defaultdict[int, int] = defaultdict(int)
        edges: list[dict[str, Any]] = []
        for row in similarities:
            a, b = int(row["job_a_id"]), int(row["job_b_id"])
            if degree[a] >= top_k and degree[b] >= top_k:
                continue
            degree[a] += 1
            degree[b] += 1
            edges.append({
                "id": f"career-sim:{a}:{b}", "source": f"job:{a}", "target": f"job:{b}",
                "type": "SIMILAR_TO", "data": {"score": float(row["score_total"]),
                    "capabilityCosine": float(row["capability_cosine"]), "coreJaccard": float(row["core_jaccard"]),
                    "sharedCapabilityCount": int(row["shared_capability_count"]), "reviewStatus": row["review_status"]},
            })
        profiled = sum(1 for row in jobs if int(row["capability_count"]) > 0)
        warnings = []
        if profiled < len(jobs):
            warnings.append(f"当前 {profiled}/{len(jobs)} 个职业具有可计算能力画像；其余职业仅显示分类位置。")
        if run and run["warning"]:
            warnings.append(str(run["warning"]))
        return {
            "schemaVersion": "2", "graphType": "career", "snapshot": snapshot,
            "nodes": nodes, "edges": edges, "combos": combos,
            "meta": {"partial": False, "stale": False, "coverage": profiled / max(1, len(jobs)), "warnings": warnings},
        }

    def job_focus(self, job_id: int, top_k: int = 8) -> dict[str, Any] | None:
        with self.database.read() as connection:
            snapshot_id, snapshot = self._snapshot(connection)
            job = connection.execute("SELECT * FROM job_positions WHERE id=?", (job_id,)).fetchone()
            if job is None:
                return None
            run = connection.execute("SELECT id FROM job_similarity_runs WHERE snapshot_id=? AND status='succeeded' ORDER BY id DESC LIMIT 1", (snapshot_id,)).fetchone()
            rows = connection.execute(
                """
                SELECT s.*,a.job_name a_name,b.job_name b_name
                FROM job_similarities s JOIN job_positions a ON a.id=s.job_a_id JOIN job_positions b ON b.id=s.job_b_id
                WHERE s.run_id=? AND (s.job_a_id=? OR s.job_b_id=?) ORDER BY s.score_total DESC LIMIT ?
                """, (int(run["id"]), job_id, job_id, top_k),
            ).fetchall() if run else []
            capabilities = connection.execute(
                """
                SELECT c.id,c.capability_name,p.weight,p.jd_count,p.evidence_count
                FROM job_capability_profiles p JOIN capability_nodes c ON c.id=p.capability_id
                WHERE p.snapshot_id=? AND p.job_id=? ORDER BY p.weight DESC LIMIT 20
                """, (snapshot_id, job_id),
            ).fetchall()
        neighbors = []
        for r in rows:
            other_id = int(r["job_b_id"] if int(r["job_a_id"]) == job_id else r["job_a_id"])
            other_name = r["b_name"] if int(r["job_a_id"]) == job_id else r["a_name"]
            neighbors.append({"id": other_id, "name": other_name, "score": float(r["score_total"]), "capabilityCosine": float(r["capability_cosine"]), "coreJaccard": float(r["core_jaccard"]), "sharedCapabilityCount": int(r["shared_capability_count"])})
        return {"job": {"id": job_id, "name": job["job_name"], "categoryL1": job["category_l1"], "categoryL2": job["category_l2"]}, "snapshot": snapshot, "neighbors": neighbors, "capabilities": [{"id": int(r["id"]), "name": r["capability_name"], "weight": float(r["weight"]), "jdCount": int(r["jd_count"]), "evidenceCount": int(r["evidence_count"])} for r in capabilities]}

    def similarity_detail(self, job_a: int, job_b: int) -> dict[str, Any] | None:
        a, b = sorted((job_a, job_b))
        with self.database.read() as connection:
            row = connection.execute(
                """
                SELECT s.*,c.semantic_score,c.title_score,c.compatibility_score,c.threshold_version,c.decision_band,
                       ja.job_name a_name,jb.job_name b_name
                FROM job_similarities s JOIN job_positions ja ON ja.id=s.job_a_id JOIN job_positions jb ON jb.id=s.job_b_id
                LEFT JOIN job_similarity_components c ON c.run_id=s.run_id AND c.job_a_id=s.job_a_id AND c.job_b_id=s.job_b_id
                WHERE s.job_a_id=? AND s.job_b_id=? ORDER BY s.run_id DESC LIMIT 1
                """, (a, b),
            ).fetchone()
            if row is None:
                return None
            shared = connection.execute(
                """
                SELECT c.id,c.capability_name,pa.weight weight_a,pb.weight weight_b
                FROM job_capability_profiles pa JOIN job_capability_profiles pb ON pb.snapshot_id=pa.snapshot_id AND pb.capability_id=pa.capability_id
                JOIN capability_nodes c ON c.id=pa.capability_id
                WHERE pa.snapshot_id=? AND pa.job_id=? AND pb.job_id=?
                ORDER BY pa.weight*pb.weight DESC LIMIT 20
                """, (int(row["snapshot_id"]), a, b),
            ).fetchall()
        return {"jobA": {"id": a, "name": row["a_name"]}, "jobB": {"id": b, "name": row["b_name"]}, "score": float(row["score_total"]), "components": {"capability": float(row["capability_cosine"]), "coreJaccard": float(row["core_jaccard"]), "hierarchy": float(row["hierarchy_score"]), "semantic": row["semantic_score"], "title": row["title_score"], "compatibility": row["compatibility_score"]}, "sharedCapabilities": [{"id": int(r["id"]), "name": r["capability_name"], "weightA": float(r["weight_a"]), "weightB": float(r["weight_b"])} for r in shared], "algorithmVersion": row["algorithm_version"], "thresholdVersion": row["threshold_version"], "decisionBand": row["decision_band"], "reviewStatus": row["review_status"]}

    def create_run(self, payload: dict[str, Any], idempotency_key: str | None = None) -> tuple[int, bool]:
        source = payload.get("source") or "manual"
        raw_jd_id = payload.get("rawJdId")
        job = payload.get("job") or {}
        input_text = compose_embedding_text(job) if source != "raw_jd" else f"raw_jd:{raw_jd_id}"
        key = idempotency_key or hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.database.write() as connection:
            existing = connection.execute("SELECT id FROM vectorization_runs WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                return int(existing["id"]), False
            model = connection.execute("SELECT id FROM embedding_models WHERE model_code='bge-small-zh-v1.5'").fetchone()
            cursor = connection.execute(
                """
                INSERT INTO vectorization_runs(idempotency_key,source_type,raw_jd_id,batch_id,model_id,input_json,input_text_hash)
                VALUES (?,?,?,?,?,?,?)
                """, (key, source, raw_jd_id, payload.get("batchId"), int(model["id"]) if model else None,
                       json.dumps(payload, ensure_ascii=False), text_hash(input_text)),
            )
            return int(cursor.lastrowid), True

    def run_result(self, run_id: int) -> dict[str, Any] | None:
        with self.database.read() as connection:
            run = connection.execute("SELECT * FROM v_vectorization_run_summary WHERE id=?", (run_id,)).fetchone()
            source = connection.execute("SELECT input_json,created_at,updated_at FROM vectorization_runs WHERE id=?", (run_id,)).fetchone()
            if run is None or source is None:
                return None
            payload = _json(source["input_json"], {})
            candidates = connection.execute(
                """
                SELECT c.*,j.job_name,j.category_l1,j.category_l2
                FROM job_match_candidates c JOIN job_positions j ON j.id=c.candidate_job_id
                WHERE c.run_id=? ORDER BY c.rank_no
                """, (run_id,),
            ).fetchall()
            decision = connection.execute("SELECT * FROM job_match_decisions WHERE run_id=?", (run_id,)).fetchone()
        return {
            "id": run_id, "source": run["source_type"], "rawJdId": run["raw_jd_id"], "status": run["status"],
            "progress": float(run["progress"]), "semanticAvailable": bool(run["semantic_available"]),
            "capabilityCount": int(run["capability_count"]), "candidateCount": int(run["candidate_count"]),
            "model": {"code": run["model_code"], "name": run["model_name"], "revision": run["model_revision"], "dimensions": run["dimensions"]},
            "warnings": _json(run["warning_json"], []), "error": run["error_message"],
            "createdAt": source["created_at"], "updatedAt": source["updated_at"], "resultSummary": payload.get("resultSummary"),
            "candidates": [{
                "id": int(r["id"]), "rank": int(r["rank_no"]), "jobId": int(r["candidate_job_id"]), "jobName": r["job_name"],
                "categoryL1": r["category_l1"], "categoryL2": r["category_l2"], "suggestion": r["suggestion"],
                "score": float(r["score_total"]), "coverage": float(r["coverage"]),
                "components": {"capability": float(r["capability_score"]), "l3": float(r["capability_l3_cosine"]), "l2": float(r["capability_l2_cosine"]), "l1": float(r["capability_l1_cosine"]), "semantic": r["semantic_score"], "coreJaccard": float(r["core_jaccard"]), "title": float(r["title_score"]), "compatibility": float(r["compatibility_score"])},
                "explanation": _json(r["explanation_json"], {}),
            } for r in candidates],
            "decision": dict(decision) if decision else None,
        }

    def decide_match(self, payload: dict[str, Any]) -> int:
        run_id = int(payload["runId"])
        decision = str(payload["decision"])
        target_job_id = payload.get("targetJobId")
        candidate_id = payload.get("candidateId")
        with self.database.write() as connection:
            run = connection.execute("SELECT raw_jd_id,input_json,status FROM vectorization_runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise LookupError("run not found")
            created_job_id = None
            if decision == "NEW_CAREER_CANDIDATE":
                job = _json(run["input_json"], {}).get("job") or {}
                title = str(job.get("title") or f"待命名职业-{run_id}").strip()
                cursor = connection.execute(
                    """
                    INSERT INTO job_positions(job_name,job_code,category_l1,category_l2,is_emerging,standardization_level,
                                              core_responsibilities,confidence_score,is_verified,version)
                    VALUES (?,?,?,?,1,'emerging',?,0.5,0,1)
                    """, (title, f"NEW-{run_id:05d}", payload.get("categoryL1") or "研究、设计与算法", payload.get("categoryL2") or "待审核新职业", job.get("responsibilities")),
                )
                created_job_id = int(cursor.lastrowid)
                target_job_id = created_job_id
            applied = decision in {"SAME_CAREER", "NEW_CAREER_CANDIDATE"} and run["raw_jd_id"] is not None and target_job_id is not None
            if applied:
                connection.execute("UPDATE raw_jd_documents SET mapped_job_id=? WHERE id=?", (target_job_id, int(run["raw_jd_id"])))
            cursor = connection.execute(
                """
                INSERT INTO job_match_decisions(run_id,candidate_id,decision,target_job_id,created_job_id,reviewer,review_note,applied,applied_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """, (run_id, candidate_id, decision, target_job_id, created_job_id, payload.get("reviewer") or "local-admin", payload.get("note"), 1 if applied else 0, _utc_now() if applied else None),
            )
            return int(cursor.lastrowid)

    def capability_candidates(self, status: str = "pending") -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                "SELECT * FROM capability_candidates WHERE status=? ORDER BY confidence DESC,created_at LIMIT 200", (status,)
            ).fetchall()
        return [dict(row) for row in rows]

    def decide_capability_candidate(self, candidate_id: int, payload: dict[str, Any]) -> None:
        with self.database.write() as connection:
            row = connection.execute("SELECT * FROM capability_candidates WHERE id=?", (candidate_id,)).fetchone()
            if row is None:
                raise LookupError("capability candidate not found")
            status = payload.get("status")
            reviewed_capability_id = payload.get("capabilityId")
            connection.execute(
                """
                UPDATE capability_candidates SET status=?,reviewed_capability_id=?,reviewer=?,review_note=?,reviewed_at=? WHERE id=?
                """, (status, reviewed_capability_id, payload.get("reviewer") or "local-admin", payload.get("note"), _utc_now(), candidate_id),
            )

    def career_communities(self) -> dict[str, Any]:
        graph = self.career_graph(top_k=8, threshold=0.25)
        adjacency: defaultdict[str, set[str]] = defaultdict(set)
        for edge in graph["edges"]:
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])
        unseen = {node["id"] for node in graph["nodes"]}
        communities = []
        while unseen:
            start = min(unseen)
            stack = [start]
            component = []
            unseen.remove(start)
            while stack:
                current = stack.pop()
                component.append(current)
                for neighbor in adjacency[current] & unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
            communities.append({"id": len(communities) + 1, "jobIds": component, "size": len(component)})
        communities.sort(key=lambda item: (-item["size"], item["id"]))
        return {"snapshot": graph["snapshot"], "communities": communities, "method": "reviewed-similarity-connected-components-v1", "note": "数据聚类模式仅用于观察，不覆盖六大标准分类。"}
