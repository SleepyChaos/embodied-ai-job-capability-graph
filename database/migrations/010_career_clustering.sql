-- LLM career clustering over approved job-capability profiles.
-- A career unit remains the smallest job node; clusters are an additional grouping layer.

ALTER TABLE career_directions ADD COLUMN description TEXT;
ALTER TABLE career_sub_directions ADD COLUMN description TEXT;

UPDATE career_directions SET description =
  CASE code
    WHEN 'D1' THEN '负责企业方向、经营决策、资源统筹与核心职能管理。'
    WHEN 'D2' THEN '负责基础研究、智能算法、系统架构与产品方案设计。'
    WHEN 'D3' THEN '负责软件、仿真、硬件、系统集成与数据工程实现。'
    WHEN 'D4' THEN '负责测试验证、生产制造、质量与供应链保障。'
    WHEN 'D5' THEN '负责市场、销售、业务拓展、部署交付与客户成功。'
    WHEN 'D6' THEN '负责人力、财务、法务、行政与专业支撑。'
  END;

UPDATE career_sub_directions SET description =
  CASE code
    WHEN '1.1' THEN '企业创始人及最高决策岗位，负责组织长期方向与重大决策。'
    WHEN '1.2' THEN '负责战略规划、业务经营、投资合作与项目资源统筹。'
    WHEN '1.3' THEN '负责研发、工程、产品、生产、质量等核心职能管理。'
    WHEN '2.1' THEN '从事基础理论、前沿技术、材料、传感器与控制研究。'
    WHEN '2.2' THEN '从事机器学习、具身智能算法、感知、规划与大模型研发。'
    WHEN '2.3' THEN '负责系统、软硬件、算法、数据、安全及产品体验架构设计。'
    WHEN '3.1' THEN '负责机器人软件、应用软件、仿真与交互系统开发。'
    WHEN '3.2' THEN '负责机械、电子、电气、传感器、驱动与结构硬件开发。'
    WHEN '3.3' THEN '负责系统集成、DevOps、数据采集治理与运行维护。'
    WHEN '4.1' THEN '负责软硬件、系统、自动化、性能、安全与可靠性测试验证。'
    WHEN '4.2' THEN '负责产品总装、工艺、工业工程、产线与制造导入。'
    WHEN '4.3' THEN '负责采购、供应商、质量控制、物料与仓储管理。'
    WHEN '5.1' THEN '负责市场研究、品牌、内容、数字营销与公共关系。'
    WHEN '5.2' THEN '负责销售、渠道、商务合作、客户拓展与解决方案经营。'
    WHEN '5.3' THEN '负责现场部署、技术支持、售后运维、培训与客户成功。'
    WHEN '6.1' THEN '负责招聘、组织发展、薪酬绩效、员工关系与人才培养。'
    WHEN '6.2' THEN '负责财务分析、会计、税务、法务、合规与风险控制。'
    WHEN '6.3' THEN '负责行政设施、知识产权、标准、IT与数据安全支撑。'
  END;

CREATE TABLE career_clusters (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_direction_id    INTEGER NOT NULL REFERENCES career_sub_directions(id),
    name                TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,
    description         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    review_status       TEXT NOT NULL DEFAULT 'approved'
                        CHECK (review_status IN ('approved','pending','rejected')),
    source              TEXT NOT NULL DEFAULT 'llm_review'
                        CHECK (source IN ('llm_auto','llm_review','manual')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX ux_career_clusters_active_name
    ON career_clusters(sub_direction_id,normalized_name)
    WHERE status='active';
CREATE INDEX idx_career_clusters_sub_direction
    ON career_clusters(sub_direction_id,status);

CREATE TABLE career_clustering_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    career_unit_id      INTEGER NOT NULL REFERENCES career_units(id) ON DELETE CASCADE,
    input_hash          TEXT NOT NULL,
    model               TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','completed','completed_with_review','failed')),
    attempt_count       INTEGER NOT NULL DEFAULT 0,
    retry_reason        TEXT,
    raw_response_json   TEXT,
    error_message       TEXT,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    started_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT,
    UNIQUE(career_unit_id,input_hash,model,prompt_version)
);

CREATE INDEX idx_career_clustering_runs_unit
    ON career_clustering_runs(career_unit_id,started_at);

CREATE TABLE career_cluster_candidates (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_run_id           INTEGER NOT NULL UNIQUE
                            REFERENCES career_clustering_runs(id) ON DELETE CASCADE,
    career_unit_id          INTEGER NOT NULL REFERENCES career_units(id) ON DELETE CASCADE,
    sub_direction_id        INTEGER NOT NULL REFERENCES career_sub_directions(id),
    proposed_name           TEXT NOT NULL,
    normalized_name         TEXT NOT NULL,
    description             TEXT NOT NULL,
    profile_confidence      REAL NOT NULL CHECK (profile_confidence BETWEEN 0 AND 1),
    classification_confidence REAL NOT NULL CHECK (classification_confidence BETWEEN 0 AND 1),
    suggested_cluster_id    INTEGER REFERENCES career_clusters(id),
    suggested_relation      TEXT CHECK (
                                suggested_relation IS NULL OR
                                suggested_relation IN ('same','broader','narrower','related','different')
                            ),
    suggested_confidence    REAL CHECK (
                                suggested_confidence IS NULL OR
                                suggested_confidence BETWEEN 0 AND 1
                            ),
    reasoning               TEXT,
    capability_evidence_json TEXT NOT NULL DEFAULT '[]',
    status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','merged','rejected')),
    resolved_cluster_id     INTEGER REFERENCES career_clusters(id),
    review_note             TEXT,
    reviewed_at             TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_career_cluster_candidates_status
    ON career_cluster_candidates(status,created_at);
CREATE INDEX idx_career_cluster_candidates_unit
    ON career_cluster_candidates(career_unit_id,status);

CREATE TABLE career_cluster_memberships (
    career_unit_id      INTEGER PRIMARY KEY REFERENCES career_units(id) ON DELETE CASCADE,
    cluster_id          INTEGER NOT NULL REFERENCES career_clusters(id) ON DELETE CASCADE,
    confidence          REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    assignment_mode     TEXT NOT NULL
                        CHECK (assignment_mode IN ('auto_merge','auto_create','manual_review')),
    evidence_json       TEXT NOT NULL DEFAULT '[]',
    source_run_id       INTEGER REFERENCES career_clustering_runs(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_career_cluster_memberships_cluster
    ON career_cluster_memberships(cluster_id,confidence DESC);

INSERT INTO schema_migrations(version,description,source_sha256)
VALUES ('010','基于已审批能力画像的职业聚类与审核流程','manual-010-career-clustering');
