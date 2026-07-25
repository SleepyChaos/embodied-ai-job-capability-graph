-- Persist per-JD outcome for unattended capability extraction and career clustering.

ALTER TABLE career_units ADD COLUMN capability_extraction_status TEXT NOT NULL DEFAULT 'not_started'
    CHECK (capability_extraction_status IN ('not_started','processing','review','succeeded','failed'));
ALTER TABLE career_units ADD COLUMN capability_extraction_failure_reason TEXT;
ALTER TABLE career_units ADD COLUMN capability_extraction_status_at TEXT;

ALTER TABLE career_units ADD COLUMN career_clustering_status TEXT NOT NULL DEFAULT 'not_started'
    CHECK (career_clustering_status IN ('not_started','processing','review','succeeded','failed'));
ALTER TABLE career_units ADD COLUMN career_clustering_failure_reason TEXT;
ALTER TABLE career_units ADD COLUMN career_clustering_status_at TEXT;

UPDATE career_units
SET capability_extraction_status =
    CASE
      WHEN EXISTS (
        SELECT 1 FROM capability_candidates cand
        JOIN capability_mentions m ON m.capability_candidate_id=cand.id
        WHERE m.career_unit_id=career_units.id AND cand.status='pending'
      ) THEN 'review'
      WHEN EXISTS (
        SELECT 1 FROM job_capability_links l
        WHERE l.career_unit_id=career_units.id
          AND l.extraction_method IN ('llm','manual')
      ) THEN 'succeeded'
      WHEN EXISTS (
        SELECT 1 FROM capability_extraction_runs r
        WHERE r.career_unit_id=career_units.id AND r.status='failed'
      ) THEN 'failed'
      ELSE 'not_started'
    END,
    capability_extraction_failure_reason = (
      SELECT r.error_message FROM capability_extraction_runs r
      WHERE r.career_unit_id=career_units.id AND r.status='failed'
      ORDER BY r.id DESC LIMIT 1
    ),
    capability_extraction_status_at = (
      SELECT COALESCE(r.completed_at,r.started_at) FROM capability_extraction_runs r
      WHERE r.career_unit_id=career_units.id
      ORDER BY r.id DESC LIMIT 1
    );

UPDATE career_units
SET career_clustering_status =
    CASE
      WHEN EXISTS (
        SELECT 1 FROM career_cluster_candidates cand
        WHERE cand.career_unit_id=career_units.id AND cand.status='pending'
      ) THEN 'review'
      WHEN EXISTS (
        SELECT 1 FROM career_cluster_memberships m
        WHERE m.career_unit_id=career_units.id
      ) THEN 'succeeded'
      WHEN EXISTS (
        SELECT 1 FROM career_clustering_runs r
        WHERE r.career_unit_id=career_units.id AND r.status='failed'
      ) THEN 'failed'
      ELSE 'not_started'
    END,
    career_clustering_failure_reason = (
      SELECT r.error_message FROM career_clustering_runs r
      WHERE r.career_unit_id=career_units.id AND r.status='failed'
      ORDER BY r.id DESC LIMIT 1
    ),
    career_clustering_status_at = (
      SELECT COALESCE(r.completed_at,r.started_at) FROM career_clustering_runs r
      WHERE r.career_unit_id=career_units.id
      ORDER BY r.id DESC LIMIT 1
    );

CREATE INDEX idx_career_units_capability_status
    ON career_units(capability_extraction_status,id);
CREATE INDEX idx_career_units_clustering_status
    ON career_units(career_clustering_status,id);

INSERT INTO schema_migrations(version,description,source_sha256)
VALUES ('011','JD能力提取与职业聚类结果状态及失败标记','manual-011-job-pipeline-status');
