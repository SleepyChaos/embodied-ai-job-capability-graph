from __future__ import annotations

from typing import Any

from .career_clustering_service import CareerClusteringService
from .database import Database
from .llm_capability_service import CapabilityLLMService


VALID_STATUSES = {"not_started", "processing", "review", "succeeded", "failed"}
VALID_ACTIONS = {"capability", "career", "both"}


class JDPipelineService:
    def __init__(
        self,
        database: Database,
        capability_service: CapabilityLLMService,
        career_service: CareerClusteringService,
    ) -> None:
        self.database = database
        self.capability_service = capability_service
        self.career_service = career_service

    def summary(self) -> dict[str, Any]:
        with self.database.read() as conn:
            totals = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(capability_extraction_status='not_started') AS capability_not_started,
                       SUM(capability_extraction_status='processing') AS capability_processing,
                       SUM(capability_extraction_status='review') AS capability_review,
                       SUM(capability_extraction_status='succeeded') AS capability_succeeded,
                       SUM(capability_extraction_status='failed') AS capability_failed,
                       SUM(career_clustering_status='not_started') AS career_not_started,
                       SUM(career_clustering_status='processing') AS career_processing,
                       SUM(career_clustering_status='review') AS career_review,
                       SUM(career_clustering_status='succeeded') AS career_succeeded,
                       SUM(career_clustering_status='failed') AS career_failed,
                       SUM(capability_extraction_status='succeeded'
                           AND career_clustering_status IN ('not_started','failed')) AS career_ready
                FROM career_units
                """
            ).fetchone()
            sources = conn.execute(
                """
                SELECT COALESCE(NULLIF(trim(data_source),''),'未标记来源') AS name,
                       COUNT(*) AS count
                FROM career_units
                GROUP BY COALESCE(NULLIF(trim(data_source),''),'未标记来源')
                ORDER BY count DESC,name
                """
            ).fetchall()
            batch = conn.execute(
                "SELECT * FROM import_batches ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            **{key: int(value or 0) for key, value in dict(totals).items()},
            "sources": [dict(row) for row in sources],
            "latestImport": dict(batch) if batch else None,
        }

    def list_jobs(
        self,
        *,
        query: str | None = None,
        source: str | None = None,
        capability_status: str | None = None,
        career_status: str | None = None,
        page: int = 1,
        page_size: int = 30,
    ) -> dict[str, Any]:
        if capability_status and capability_status not in VALID_STATUSES:
            raise ValueError("能力提取状态筛选值无效")
        if career_status and career_status not in VALID_STATUSES:
            raise ValueError("职业聚类状态筛选值无效")
        conditions = []
        params: list[Any] = []
        if query:
            conditions.append(
                "(cu.job_title LIKE ? OR co.name LIKE ? OR CAST(cu.id AS TEXT)=?)"
            )
            pattern = f"%{query.strip()}%"
            params.extend([pattern, pattern, query.strip()])
        if source:
            conditions.append(
                "COALESCE(NULLIF(trim(cu.data_source),''),'未标记来源')=?"
            )
            params.append(source)
        if capability_status:
            conditions.append("cu.capability_extraction_status=?")
            params.append(capability_status)
        if career_status:
            conditions.append("cu.career_clustering_status=?")
            params.append(career_status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.database.read() as conn:
            total = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM career_units cu
                    LEFT JOIN companies co ON co.id=cu.company_id
                    {where}
                    """,
                    params,
                ).fetchone()[0]
            )
            rows = conn.execute(
                f"""
                SELECT cu.id,cu.job_title,cu.data_source,cu.source_platform,
                       cu.capability_extraction_status,
                       cu.capability_extraction_failure_reason,
                       cu.capability_extraction_status_at,
                       cu.career_clustering_status,
                       cu.career_clustering_failure_reason,
                       cu.career_clustering_status_at,
                       co.name AS company_name,
                       sd.code AS sub_direction_code,sd.name AS sub_direction_name,
                       cluster.id AS cluster_id,cluster.name AS cluster_name,
                       COUNT(DISTINCT capability.id) AS capability_count,
                       (SELECT attempt_count FROM capability_extraction_runs r
                        WHERE r.career_unit_id=cu.id ORDER BY r.id DESC LIMIT 1)
                         AS capability_attempt_count,
                       (SELECT attempt_count FROM career_clustering_runs r
                        WHERE r.career_unit_id=cu.id ORDER BY r.id DESC LIMIT 1)
                         AS career_attempt_count
                FROM career_units cu
                LEFT JOIN companies co ON co.id=cu.company_id
                LEFT JOIN career_sub_directions sd ON sd.id=cu.sub_direction_id
                LEFT JOIN career_cluster_memberships membership
                  ON membership.career_unit_id=cu.id
                LEFT JOIN career_clusters cluster ON cluster.id=membership.cluster_id
                LEFT JOIN job_capability_links link ON link.career_unit_id=cu.id
                LEFT JOIN capability_aliases alias ON alias.id=link.capability_alias_id
                LEFT JOIN capabilities capability
                  ON capability.id=alias.capability_id AND capability.status='active'
                {where}
                GROUP BY cu.id
                ORDER BY
                  CASE cu.capability_extraction_status
                    WHEN 'failed' THEN 0 WHEN 'review' THEN 1
                    WHEN 'processing' THEN 2 WHEN 'not_started' THEN 3 ELSE 4 END,
                  CASE cu.career_clustering_status
                    WHEN 'failed' THEN 0 WHEN 'review' THEN 1
                    WHEN 'processing' THEN 2 WHEN 'not_started' THEN 3 ELSE 4 END,
                  cu.id
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "page": {
                "page": page,
                "pageSize": page_size,
                "total": total,
            },
        }

    def process(self, career_unit_ids: list[int], action: str) -> dict[str, Any]:
        if action not in VALID_ACTIONS:
            raise ValueError("处理动作必须是 capability、career 或 both")
        unique_ids = list(dict.fromkeys(int(value) for value in career_unit_ids))
        if not unique_ids:
            raise ValueError("至少选择一条 JD")
        if len(unique_ids) > 10:
            raise ValueError("单次最多处理10条 JD")
        results = []
        for career_unit_id in unique_ids:
            with self.database.read() as conn:
                job = conn.execute(
                    """
                    SELECT id,capability_extraction_status,career_clustering_status
                    FROM career_units WHERE id=?
                    """,
                    (career_unit_id,),
                ).fetchone()
            if job is None:
                results.append(
                    {"careerUnitId": career_unit_id, "status": "failed", "error": "JD不存在"}
                )
                continue
            item: dict[str, Any] = {
                "careerUnitId": career_unit_id,
                "capability": "skipped",
                "career": "skipped",
            }
            if action in {"capability", "both"}:
                capability_status = str(job["capability_extraction_status"])
                if capability_status in {"not_started", "failed"}:
                    try:
                        result = self.capability_service.extract_career_unit(
                            career_unit_id, force=capability_status == "failed"
                        )
                        item["capability"] = result["run"]["status"]
                    except Exception as error:
                        item["capability"] = "failed"
                        item["capabilityError"] = str(error)
                else:
                    item["capability"] = capability_status
            with self.database.read() as conn:
                current = conn.execute(
                    """
                    SELECT capability_extraction_status,career_clustering_status
                    FROM career_units WHERE id=?
                    """,
                    (career_unit_id,),
                ).fetchone()
            if action in {"career", "both"}:
                if current["capability_extraction_status"] != "succeeded":
                    item["career"] = "blocked"
                    item["careerError"] = "能力提取尚未成功"
                elif current["career_clustering_status"] in {"not_started", "failed"}:
                    try:
                        result = self.career_service.cluster_career_unit(
                            career_unit_id,
                            force=current["career_clustering_status"] == "failed",
                        )
                        item["career"] = result["run"]["status"]
                    except Exception as error:
                        item["career"] = "failed"
                        item["careerError"] = str(error)
                else:
                    item["career"] = current["career_clustering_status"]
            item["status"] = (
                "failed"
                if "failed" in {item["capability"], item["career"]}
                else "completed"
            )
            results.append(item)
        return {"items": results, "count": len(results)}
