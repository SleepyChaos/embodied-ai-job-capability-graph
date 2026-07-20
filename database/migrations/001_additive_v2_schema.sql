-- Embodied AI jobs database v2 additive migration.
-- Legacy tables are intentionally left unchanged so every existing value remains intact.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    source_sha256   TEXT NOT NULL,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_code          TEXT NOT NULL UNIQUE,
    source_file         TEXT,
    source_sha256       TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    input_count         INTEGER NOT NULL DEFAULT 0 CHECK (input_count >= 0),
    accepted_count      INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
    rejected_count      INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    duplicate_count     INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
    status              TEXT NOT NULL DEFAULT 'completed'
                        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    config_json         TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
    report_json         TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(report_json)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jd_batch_memberships (
    batch_id        INTEGER NOT NULL REFERENCES ingestion_batches(id) ON DELETE CASCADE,
    jd_id           INTEGER NOT NULL REFERENCES raw_jd_documents(id) ON DELETE CASCADE,
    source_row_no   INTEGER,
    action          TEXT NOT NULL DEFAULT 'imported'
                    CHECK (action IN ('imported','updated','skipped','rejected')),
    reason          TEXT,
    PRIMARY KEY (batch_id, jd_id)
);

CREATE TABLE IF NOT EXISTS companies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_name     TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jd_company_links (
    jd_id           INTEGER PRIMARY KEY REFERENCES raw_jd_documents(id) ON DELETE CASCADE,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    confidence      REAL NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    method          TEXT NOT NULL DEFAULT 'legacy_exact',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The legacy skill_taxonomy table actually contains the job hierarchy.
-- v2 copies it into a correctly named table and keeps the legacy table for compatibility.
CREATE TABLE IF NOT EXISTS job_categories (
    id              INTEGER PRIMARY KEY,
    parent_id       INTEGER REFERENCES job_categories(id) ON DELETE RESTRICT,
    category_code   TEXT NOT NULL UNIQUE,
    category_name   TEXT NOT NULL,
    category_level  INTEGER NOT NULL CHECK (category_level BETWEEN 1 AND 3),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    description     TEXT,
    icon            TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (parent_id, category_name)
);

CREATE TABLE IF NOT EXISTS job_category_memberships (
    job_id          INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    category_id     INTEGER NOT NULL REFERENCES job_categories(id) ON DELETE RESTRICT,
    is_primary      INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0,1)),
    valid_from      TEXT,
    valid_to        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (job_id, category_id),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS skill_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id       INTEGER REFERENCES skill_categories(id) ON DELETE RESTRICT,
    category_code   TEXT NOT NULL UNIQUE,
    category_name   TEXT NOT NULL,
    category_level  INTEGER NOT NULL CHECK (category_level BETWEEN 1 AND 4),
    description     TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (parent_id, category_name)
);

CREATE TABLE IF NOT EXISTS skill_category_memberships (
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    category_id     INTEGER NOT NULL REFERENCES skill_categories(id) ON DELETE RESTRICT,
    is_primary      INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0,1)),
    confidence      REAL NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    method          TEXT NOT NULL DEFAULT 'legacy_skill_type',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (skill_id, category_id)
);

CREATE TABLE IF NOT EXISTS graph_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_code       TEXT NOT NULL UNIQUE,
    snapshot_name       TEXT NOT NULL,
    snapshot_at         TEXT NOT NULL,
    source_db_sha256    TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ready'
                        CHECK (status IN ('building','ready','failed','archived')),
    is_baseline         INTEGER NOT NULL DEFAULT 0 CHECK (is_baseline IN (0,1)),
    metrics_json        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metrics_json)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_graph_snapshots_single_baseline
    ON graph_snapshots(is_baseline) WHERE is_baseline = 1;

CREATE TABLE IF NOT EXISTS job_definition_versions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id             INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    job_id                  INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    version_no              INTEGER NOT NULL CHECK (version_no >= 1),
    job_name                TEXT NOT NULL,
    core_responsibilities   TEXT,
    typical_scenarios       TEXT,
    career_path             TEXT,
    seniority_levels        TEXT,
    confidence_score        REAL CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
    is_verified             INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0,1)),
    valid_from              TEXT NOT NULL,
    valid_to                TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (snapshot_id, job_id),
    UNIQUE (job_id, version_no),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS skill_definition_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id         INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    skill_id            INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    version_no          INTEGER NOT NULL CHECK (version_no >= 1),
    skill_name          TEXT NOT NULL,
    skill_type          TEXT NOT NULL,
    difficulty_level    TEXT,
    description         TEXT,
    demand_trend        TEXT,
    demand_score        REAL CHECK (demand_score IS NULL OR demand_score BETWEEN 0 AND 1),
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (snapshot_id, skill_id),
    UNIQUE (skill_id, version_no),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS job_skill_evidence (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    mapping_id              INTEGER NOT NULL REFERENCES job_skill_mapping(id) ON DELETE CASCADE,
    jd_id                   INTEGER NOT NULL REFERENCES raw_jd_documents(id) ON DELETE CASCADE,
    evidence_role           TEXT NOT NULL DEFAULT 'supports'
                            CHECK (evidence_role IN ('supports','contradicts','mentions','legacy_support')),
    evidence_text           TEXT,
    char_start              INTEGER CHECK (char_start IS NULL OR char_start >= 0),
    char_end                INTEGER CHECK (char_end IS NULL OR char_end >= 0),
    extraction_method       TEXT NOT NULL DEFAULT 'legacy_import',
    extraction_confidence   REAL CHECK (extraction_confidence IS NULL OR extraction_confidence BETWEEN 0 AND 1),
    is_human_verified       INTEGER NOT NULL DEFAULT 0 CHECK (is_human_verified IN (0,1)),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (mapping_id, jd_id),
    CHECK (char_end IS NULL OR char_start IS NULL OR char_end >= char_start)
);

CREATE TABLE IF NOT EXISTS graph_snapshot_job_skills (
    snapshot_id             INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    mapping_id              INTEGER NOT NULL REFERENCES job_skill_mapping(id) ON DELETE RESTRICT,
    job_id                  INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    skill_id                INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    relation_version        INTEGER NOT NULL CHECK (relation_version >= 1),
    importance              TEXT NOT NULL CHECK (importance IN ('required','preferred','optional')),
    proficiency_required    TEXT,
    weight                  REAL CHECK (weight IS NULL OR weight BETWEEN 0 AND 1),
    confidence              REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    status                  TEXT NOT NULL CHECK (status IN ('active','removed','deprecated')),
    evidence_count          INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    valid_from              TEXT NOT NULL,
    valid_to                TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (snapshot_id, job_id, skill_id),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS change_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    from_snapshot_id    INTEGER REFERENCES graph_snapshots(id) ON DELETE RESTRICT,
    to_snapshot_id      INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    entity_type         TEXT NOT NULL CHECK (entity_type IN ('job','skill','job_skill_relation')),
    entity_key          TEXT NOT NULL,
    change_type         TEXT NOT NULL CHECK (change_type IN ('added','removed','modified','unchanged')),
    field_name          TEXT,
    old_value_json      TEXT CHECK (old_value_json IS NULL OR json_valid(old_value_json)),
    new_value_json      TEXT CHECK (new_value_json IS NULL OR json_valid(new_value_json)),
    explanation         TEXT,
    evidence_count      INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    confidence          REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (to_snapshot_id, entity_type, entity_key, change_type, field_name)
);

CREATE TABLE IF NOT EXISTS manual_review_tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type           TEXT NOT NULL CHECK (task_type IN ('job_mapping','skill_extraction','relation_change','hallucination','data_quality')),
    target_type         TEXT NOT NULL,
    target_id           INTEGER NOT NULL,
    priority            INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 3),
    reason              TEXT NOT NULL,
    payload_json        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload_json)),
    status              TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_review','approved','rejected','closed')),
    assigned_to         TEXT,
    resolution_note     TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at         TEXT
);

CREATE TABLE IF NOT EXISTS graph_sync_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id         INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    target_type         TEXT NOT NULL DEFAULT 'neo4j' CHECK (target_type IN ('neo4j','json','graphml','other')),
    target_name         TEXT NOT NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('full','incremental','validate')),
    status              TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','succeeded','failed','cancelled')),
    idempotency_key     TEXT NOT NULL UNIQUE,
    nodes_written       INTEGER NOT NULL DEFAULT 0 CHECK (nodes_written >= 0),
    edges_written       INTEGER NOT NULL DEFAULT 0 CHECK (edges_written >= 0),
    error_message       TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jd_batch_jd ON jd_batch_memberships(jd_id);
CREATE INDEX IF NOT EXISTS idx_jd_company_company ON jd_company_links(company_id);
CREATE INDEX IF NOT EXISTS idx_job_category_category ON job_category_memberships(category_id);
CREATE INDEX IF NOT EXISTS idx_skill_category_category ON skill_category_memberships(category_id);
CREATE INDEX IF NOT EXISTS idx_job_skill_evidence_jd ON job_skill_evidence(jd_id);
CREATE INDEX IF NOT EXISTS idx_job_skill_evidence_mapping ON job_skill_evidence(mapping_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_job_skills_job ON graph_snapshot_job_skills(snapshot_id, job_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_job_skills_skill ON graph_snapshot_job_skills(snapshot_id, skill_id);
CREATE INDEX IF NOT EXISTS idx_change_events_snapshot ON change_events(to_snapshot_id, change_type);
CREATE INDEX IF NOT EXISTS idx_review_tasks_status ON manual_review_tasks(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_sync_runs_snapshot ON graph_sync_runs(snapshot_id, created_at);

CREATE VIEW IF NOT EXISTS v_job_skill_current AS
SELECT m.*
FROM job_skill_mapping m
WHERE m.version = (
    SELECT MAX(m2.version)
    FROM job_skill_mapping m2
    WHERE m2.job_id = m.job_id AND m2.skill_id = m.skill_id
)
AND m.status = 'active';

CREATE VIEW IF NOT EXISTS v_job_skill_evidence_detail AS
SELECT
    e.id AS evidence_id,
    e.mapping_id,
    m.job_id,
    jp.job_name,
    m.skill_id,
    s.skill_name,
    e.jd_id,
    r.raw_title,
    r.company_name,
    r.fetch_url,
    r.published_at,
    r.fetched_at,
    d.source_name,
    e.evidence_role,
    e.evidence_text,
    e.extraction_method,
    e.extraction_confidence,
    e.is_human_verified
FROM job_skill_evidence e
JOIN job_skill_mapping m ON m.id = e.mapping_id
JOIN job_positions jp ON jp.id = m.job_id
JOIN skills s ON s.id = m.skill_id
JOIN raw_jd_documents r ON r.id = e.jd_id
LEFT JOIN data_sources d ON d.id = r.source_id;

CREATE VIEW IF NOT EXISTS v_graph_nodes AS
SELECT 'job_category:' || id AS node_key, 'JobCategory' AS node_type, category_name AS label,
       json_object('id',id,'level',category_level,'parent_id',parent_id,'code',category_code) AS properties_json
FROM job_categories
UNION ALL
SELECT 'job:' || id, 'Job', job_name,
       json_object('id',id,'code',job_code,'category_l1',category_l1,'category_l2',category_l2,'is_emerging',is_emerging,'version',version)
FROM job_positions
UNION ALL
SELECT 'skill_category:' || id, 'SkillCategory', category_name,
       json_object('id',id,'level',category_level,'parent_id',parent_id,'code',category_code)
FROM skill_categories
UNION ALL
SELECT 'skill:' || id, 'Skill', skill_name,
       json_object('id',id,'code',skill_code,'type',skill_type,'trend',demand_trend,'demand_score',demand_score)
FROM skills
UNION ALL
SELECT 'company:' || id, 'Company', display_name,
       json_object('id',id,'normalized_name',normalized_name)
FROM companies
UNION ALL
SELECT 'source:' || id, 'DataSource', source_name,
       json_object('id',id,'source_type',source_type,'credibility',credibility,'active',is_active)
FROM data_sources;

CREATE VIEW IF NOT EXISTS v_graph_edges AS
SELECT 'job_category:' || parent_id || '->job_category:' || id AS edge_key,
       'HAS_CHILD_CATEGORY' AS edge_type,
       'job_category:' || parent_id AS source_key,
       'job_category:' || id AS target_key,
       json_object('sort_order',sort_order) AS properties_json
FROM job_categories WHERE parent_id IS NOT NULL
UNION ALL
SELECT 'job_category:' || category_id || '->job:' || job_id,
       'CONTAINS_JOB', 'job_category:' || category_id, 'job:' || job_id,
       json_object('primary',is_primary,'valid_from',valid_from,'valid_to',valid_to)
FROM job_category_memberships
UNION ALL
SELECT 'skill_category:' || parent_id || '->skill_category:' || id,
       'HAS_CHILD_CATEGORY', 'skill_category:' || parent_id, 'skill_category:' || id,
       json_object('sort_order',sort_order)
FROM skill_categories WHERE parent_id IS NOT NULL
UNION ALL
SELECT 'skill_category:' || category_id || '->skill:' || skill_id,
       'CONTAINS_SKILL', 'skill_category:' || category_id, 'skill:' || skill_id,
       json_object('primary',is_primary,'confidence',confidence,'method',method)
FROM skill_category_memberships
UNION ALL
SELECT 'job:' || job_id || '->skill:' || skill_id,
       'REQUIRES_SKILL', 'job:' || job_id, 'skill:' || skill_id,
       json_object('mapping_id',id,'importance',importance,'proficiency',proficiency_required,'weight',weight,'confidence',confidence,'version',version)
FROM v_job_skill_current
UNION ALL
SELECT 'company:' || l.company_id || '->job:' || r.mapped_job_id,
       'RECRUITS_FOR', 'company:' || l.company_id, 'job:' || r.mapped_job_id,
       json_object('jd_count',count(*))
FROM jd_company_links l
JOIN raw_jd_documents r ON r.id = l.jd_id
WHERE r.mapped_job_id IS NOT NULL
GROUP BY l.company_id, r.mapped_job_id
UNION ALL
SELECT 'source:' || r.source_id || '->job:' || r.mapped_job_id,
       'SUPPORTS_JOB', 'source:' || r.source_id, 'job:' || r.mapped_job_id,
       json_object('jd_count',count(*))
FROM raw_jd_documents r
WHERE r.source_id IS NOT NULL AND r.mapped_job_id IS NOT NULL
GROUP BY r.source_id, r.mapped_job_id;

-- Future writes to mapped_job_id receive FK-equivalent protection without rebuilding the legacy table.
CREATE TRIGGER IF NOT EXISTS trg_raw_jd_mapped_job_insert
BEFORE INSERT ON raw_jd_documents
WHEN NEW.mapped_job_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM job_positions WHERE id = NEW.mapped_job_id)
BEGIN
    SELECT RAISE(ABORT, 'raw_jd_documents.mapped_job_id references a missing job_positions row');
END;

CREATE TRIGGER IF NOT EXISTS trg_raw_jd_mapped_job_update
BEFORE UPDATE OF mapped_job_id ON raw_jd_documents
WHEN NEW.mapped_job_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM job_positions WHERE id = NEW.mapped_job_id)
BEGIN
    SELECT RAISE(ABORT, 'raw_jd_documents.mapped_job_id references a missing job_positions row');
END;

CREATE TRIGGER IF NOT EXISTS trg_job_skill_mapping_json_insert
BEFORE INSERT ON job_skill_mapping
WHEN NEW.source_jd_ids IS NOT NULL AND json_valid(NEW.source_jd_ids) = 0
BEGIN
    SELECT RAISE(ABORT, 'job_skill_mapping.source_jd_ids must be valid JSON');
END;

CREATE TRIGGER IF NOT EXISTS trg_job_skill_mapping_json_update
BEFORE UPDATE OF source_jd_ids ON job_skill_mapping
WHEN NEW.source_jd_ids IS NOT NULL AND json_valid(NEW.source_jd_ids) = 0
BEGIN
    SELECT RAISE(ABORT, 'job_skill_mapping.source_jd_ids must be valid JSON');
END;
