-- Capability ontology and career similarity schema (v3).
-- This migration is additive: no v1/v2 table is altered or deleted.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ontology_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    version_code        TEXT NOT NULL UNIQUE,
    version_name        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','reviewing','ready','archived')),
    source_type         TEXT NOT NULL DEFAULT 'expert_seed',
    description         TEXT,
    is_current          INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    published_at        TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_ontology_versions_current
ON ontology_versions(is_current) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS capability_nodes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ontology_version_id INTEGER NOT NULL REFERENCES ontology_versions(id) ON DELETE RESTRICT,
    parent_id           INTEGER REFERENCES capability_nodes(id) ON DELETE RESTRICT,
    capability_code     TEXT NOT NULL UNIQUE,
    capability_name     TEXT NOT NULL,
    capability_name_en  TEXT,
    level               INTEGER NOT NULL CHECK (level BETWEEN 0 AND 3),
    node_kind           TEXT NOT NULL
                        CHECK (node_kind IN ('root','domain','category','capability','variant')),
    description         TEXT,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    source_type         TEXT NOT NULL DEFAULT 'expert_seed'
                        CHECK (source_type IN ('talent_map','expert_seed','legacy_skill','jd_induced','hybrid')),
    confidence          REAL NOT NULL DEFAULT 0.60 CHECK (confidence BETWEEN 0 AND 1),
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','deprecated','merged')),
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (ontology_version_id, parent_id, capability_name),
    CHECK ((level = 0 AND parent_id IS NULL AND node_kind = 'root')
        OR (level > 0 AND parent_id IS NOT NULL)),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS capability_aliases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id       INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE CASCADE,
    alias_name          TEXT NOT NULL,
    normalized_alias    TEXT NOT NULL,
    alias_type          TEXT NOT NULL
                        CHECK (alias_type IN ('synonym','abbreviation','spelling','translation','legacy_label')),
    source              TEXT NOT NULL DEFAULT 'legacy_skill',
    usage_frequency     INTEGER NOT NULL DEFAULT 0 CHECK (usage_frequency >= 0),
    confidence          REAL NOT NULL DEFAULT 0.80 CHECK (confidence BETWEEN 0 AND 1),
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (capability_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS capability_relations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_capability_id    INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE CASCADE,
    target_capability_id    INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE CASCADE,
    relation_type           TEXT NOT NULL
                            CHECK (relation_type IN ('VARIANT_OF','PREREQUISITE_OF','RELATED_TO','BROADER_THAN')),
    weight                  REAL NOT NULL DEFAULT 0.50 CHECK (weight BETWEEN 0 AND 1),
    confidence              REAL NOT NULL DEFAULT 0.60 CHECK (confidence BETWEEN 0 AND 1),
    evidence_count          INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    source_type             TEXT NOT NULL DEFAULT 'expert_seed',
    review_status           TEXT NOT NULL DEFAULT 'pending'
                            CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source_capability_id, target_capability_id, relation_type),
    CHECK (source_capability_id <> target_capability_id)
);

CREATE TABLE IF NOT EXISTS skill_capability_mappings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id            INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    capability_id       INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE RESTRICT,
    mapping_type        TEXT NOT NULL
                        CHECK (mapping_type IN ('exact','broader','narrower','related','variant')),
    method              TEXT NOT NULL
                        CHECK (method IN ('rule','dictionary','embedding','llm','manual','legacy_seed')),
    confidence          REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    is_primary          INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0,1)),
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    reviewed_by         TEXT,
    review_note         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (skill_id, capability_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_skill_capability_primary
ON skill_capability_mappings(skill_id) WHERE is_primary = 1;

CREATE TABLE IF NOT EXISTS career_aliases_v3 (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    alias_name          TEXT NOT NULL,
    normalized_alias    TEXT NOT NULL,
    alias_type          TEXT NOT NULL
                        CHECK (alias_type IN ('synonym','abbreviation','translation','legacy_label','market_title')),
    source              TEXT NOT NULL,
    usage_frequency     INTEGER NOT NULL DEFAULT 0 CHECK (usage_frequency >= 0),
    confidence          REAL NOT NULL DEFAULT 0.80 CHECK (confidence BETWEEN 0 AND 1),
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (job_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS job_capability_profiles (
    snapshot_id             INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    job_id                  INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    capability_id           INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE RESTRICT,
    importance              TEXT NOT NULL DEFAULT 'unspecified'
                            CHECK (importance IN ('required','preferred','optional','unspecified')),
    proficiency_required    TEXT,
    mention_count           INTEGER NOT NULL DEFAULT 0 CHECK (mention_count >= 0),
    jd_count                INTEGER NOT NULL DEFAULT 0 CHECK (jd_count >= 0),
    source_count            INTEGER NOT NULL DEFAULT 0 CHECK (source_count >= 0),
    weight                  REAL NOT NULL CHECK (weight BETWEEN 0 AND 1),
    confidence              REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence_count          INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    calculation_version     TEXT NOT NULL,
    review_status           TEXT NOT NULL DEFAULT 'pending'
                            CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    valid_from              TEXT NOT NULL,
    valid_to                TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (snapshot_id, job_id, capability_id),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS job_similarity_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id         INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    algorithm_version   TEXT NOT NULL,
    config_json         TEXT NOT NULL CHECK (json_valid(config_json)),
    job_count           INTEGER NOT NULL CHECK (job_count >= 0),
    candidate_pairs     INTEGER NOT NULL CHECK (candidate_pairs >= 0),
    retained_pairs      INTEGER NOT NULL CHECK (retained_pairs >= 0),
    status              TEXT NOT NULL DEFAULT 'succeeded'
                        CHECK (status IN ('running','succeeded','failed')),
    warning             TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (snapshot_id, algorithm_version)
);

CREATE TABLE IF NOT EXISTS job_similarities (
    run_id                      INTEGER NOT NULL REFERENCES job_similarity_runs(id) ON DELETE CASCADE,
    snapshot_id                 INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    job_a_id                    INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    job_b_id                    INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    score_total                 REAL NOT NULL CHECK (score_total BETWEEN 0 AND 1),
    capability_cosine           REAL NOT NULL CHECK (capability_cosine BETWEEN 0 AND 1),
    core_jaccard                REAL NOT NULL CHECK (core_jaccard BETWEEN 0 AND 1),
    hierarchy_score             REAL NOT NULL CHECK (hierarchy_score BETWEEN 0 AND 1),
    shared_capability_count     INTEGER NOT NULL CHECK (shared_capability_count >= 0),
    coverage_a                  REAL NOT NULL CHECK (coverage_a BETWEEN 0 AND 1),
    coverage_b                  REAL NOT NULL CHECK (coverage_b BETWEEN 0 AND 1),
    algorithm_version           TEXT NOT NULL,
    review_status               TEXT NOT NULL DEFAULT 'pending'
                                CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, job_a_id, job_b_id),
    CHECK (job_a_id < job_b_id)
);

CREATE TABLE IF NOT EXISTS job_similarity_explanations (
    run_id                  INTEGER NOT NULL,
    job_a_id                INTEGER NOT NULL,
    job_b_id                INTEGER NOT NULL,
    capability_id           INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE RESTRICT,
    contribution            REAL NOT NULL CHECK (contribution BETWEEN 0 AND 1),
    rank_no                 INTEGER NOT NULL CHECK (rank_no >= 1),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, job_a_id, job_b_id, capability_id),
    FOREIGN KEY (run_id, job_a_id, job_b_id)
        REFERENCES job_similarities(run_id, job_a_id, job_b_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS career_communities (
    snapshot_id         INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    algorithm_version   TEXT NOT NULL,
    job_id              INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    community_code      TEXT NOT NULL,
    membership_score    REAL NOT NULL DEFAULT 1.0 CHECK (membership_score BETWEEN 0 AND 1),
    is_cross_domain     INTEGER NOT NULL DEFAULT 0 CHECK (is_cross_domain IN (0,1)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (snapshot_id, algorithm_version, job_id)
);

CREATE TABLE IF NOT EXISTS graph_layout_cache (
    snapshot_id         INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    graph_type          TEXT NOT NULL CHECK (graph_type IN ('capability','career_taxonomy','career_community','career_focus')),
    filter_hash         TEXT NOT NULL,
    element_id          TEXT NOT NULL,
    x                   REAL NOT NULL,
    y                   REAL NOT NULL,
    pinned              INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0,1)),
    layout_version      TEXT NOT NULL,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (snapshot_id, graph_type, filter_hash, element_id)
);

CREATE INDEX IF NOT EXISTS idx_capability_nodes_parent
ON capability_nodes(parent_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_capability_nodes_level
ON capability_nodes(level, node_kind, status);

CREATE INDEX IF NOT EXISTS idx_capability_alias_normalized
ON capability_aliases(normalized_alias);

CREATE INDEX IF NOT EXISTS idx_capability_relations_target
ON capability_relations(target_capability_id, relation_type);

CREATE INDEX IF NOT EXISTS idx_skill_capability_capability
ON skill_capability_mappings(capability_id, review_status);

CREATE INDEX IF NOT EXISTS idx_career_alias_normalized
ON career_aliases_v3(normalized_alias);

CREATE INDEX IF NOT EXISTS idx_job_capability_job
ON job_capability_profiles(snapshot_id, job_id, weight DESC);

CREATE INDEX IF NOT EXISTS idx_job_capability_capability
ON job_capability_profiles(snapshot_id, capability_id, weight DESC);

CREATE INDEX IF NOT EXISTS idx_job_similarity_a
ON job_similarities(snapshot_id, job_a_id, score_total DESC);

CREATE INDEX IF NOT EXISTS idx_job_similarity_b
ON job_similarities(snapshot_id, job_b_id, score_total DESC);

CREATE TRIGGER IF NOT EXISTS trg_capability_parent_level_insert
BEFORE INSERT ON capability_nodes
WHEN NEW.parent_id IS NOT NULL
 AND NOT EXISTS (
     SELECT 1 FROM capability_nodes p
     WHERE p.id = NEW.parent_id
       AND p.ontology_version_id = NEW.ontology_version_id
       AND p.level = NEW.level - 1
 )
BEGIN
    SELECT RAISE(ABORT, 'capability parent must belong to the same ontology and be exactly one level above');
END;

CREATE TRIGGER IF NOT EXISTS trg_capability_parent_level_update
BEFORE UPDATE OF parent_id, level, ontology_version_id ON capability_nodes
WHEN NEW.parent_id IS NOT NULL
 AND NOT EXISTS (
     SELECT 1 FROM capability_nodes p
     WHERE p.id = NEW.parent_id
       AND p.ontology_version_id = NEW.ontology_version_id
       AND p.level = NEW.level - 1
 )
BEGIN
    SELECT RAISE(ABORT, 'capability parent must belong to the same ontology and be exactly one level above');
END;

CREATE TRIGGER IF NOT EXISTS trg_capability_cycle_update
BEFORE UPDATE OF parent_id ON capability_nodes
WHEN NEW.parent_id IS NOT NULL
BEGIN
    WITH RECURSIVE descendants(id) AS (
        SELECT OLD.id
        UNION ALL
        SELECT c.id FROM capability_nodes c JOIN descendants d ON c.parent_id = d.id
    )
    SELECT CASE WHEN NEW.parent_id IN descendants
        THEN RAISE(ABORT, 'capability hierarchy cycle detected') END;
END;

CREATE VIEW IF NOT EXISTS v_capability_tree AS
WITH RECURSIVE tree AS (
    SELECT
        n.id, n.parent_id, n.capability_code, n.capability_name,
        n.capability_name_en, n.level, n.node_kind, n.sort_order,
        n.source_type, n.confidence, n.review_status, n.status,
        n.capability_name AS path_name,
        n.capability_code AS path_code
    FROM capability_nodes n
    WHERE n.parent_id IS NULL
    UNION ALL
    SELECT
        c.id, c.parent_id, c.capability_code, c.capability_name,
        c.capability_name_en, c.level, c.node_kind, c.sort_order,
        c.source_type, c.confidence, c.review_status, c.status,
        tree.path_name || ' > ' || c.capability_name,
        tree.path_code || '/' || c.capability_code
    FROM capability_nodes c
    JOIN tree ON c.parent_id = tree.id
)
SELECT * FROM tree;

CREATE VIEW IF NOT EXISTS v_capability_summary AS
SELECT
    n.id, n.parent_id, n.capability_code, n.capability_name,
    n.level, n.node_kind, n.sort_order, n.source_type,
    n.confidence, n.review_status, n.status,
    (SELECT COUNT(*) FROM capability_nodes c WHERE c.parent_id=n.id AND c.status='active') AS child_count,
    (SELECT COUNT(*) FROM capability_aliases a WHERE a.capability_id=n.id) AS alias_count,
    (SELECT COUNT(DISTINCT p.job_id) FROM job_capability_profiles p WHERE p.capability_id=n.id) AS job_count
FROM capability_nodes n;

CREATE VIEW IF NOT EXISTS v_job_capability_detail AS
SELECT
    p.snapshot_id, p.job_id, j.job_name,
    p.capability_id, c.capability_code, c.capability_name,
    parent.capability_name AS category_name,
    domain.capability_name AS domain_name,
    p.importance, p.proficiency_required, p.mention_count,
    p.jd_count, p.source_count, p.weight, p.confidence,
    p.evidence_count, p.calculation_version, p.review_status
FROM job_capability_profiles p
JOIN job_positions j ON j.id=p.job_id
JOIN capability_nodes c ON c.id=p.capability_id
LEFT JOIN capability_nodes parent ON parent.id=c.parent_id
LEFT JOIN capability_nodes domain ON domain.id=parent.parent_id;

CREATE VIEW IF NOT EXISTS v_job_similarity_detail AS
SELECT
    s.run_id, s.snapshot_id, s.job_a_id, a.job_name AS job_a_name,
    s.job_b_id, b.job_name AS job_b_name, s.score_total,
    s.capability_cosine, s.core_jaccard, s.hierarchy_score,
    s.shared_capability_count, s.coverage_a, s.coverage_b,
    s.algorithm_version, s.review_status, s.created_at
FROM job_similarities s
JOIN job_positions a ON a.id=s.job_a_id
JOIN job_positions b ON b.id=s.job_b_id;

CREATE VIEW IF NOT EXISTS v_graph_v3_nodes AS
SELECT
    'capability:' || id AS node_key,
    CASE node_kind
        WHEN 'root' THEN 'CapabilityRoot'
        WHEN 'domain' THEN 'CapabilityDomain'
        WHEN 'category' THEN 'CapabilityCategory'
        WHEN 'variant' THEN 'CapabilityVariant'
        ELSE 'Capability'
    END AS node_type,
    capability_name AS label,
    json_object(
        'id', id, 'code', capability_code, 'level', level,
        'kind', node_kind, 'review_status', review_status,
        'confidence', confidence
    ) AS properties_json
FROM capability_nodes
WHERE status='active'
UNION ALL
SELECT
    'career:' || id, 'Career', job_name,
    json_object(
        'id', id, 'code', job_code, 'category_l1', category_l1,
        'category_l2', category_l2, 'is_emerging', is_emerging
    )
FROM job_positions;

CREATE VIEW IF NOT EXISTS v_graph_v3_edges AS
SELECT
    'capability:' || parent_id || '->capability:' || id AS edge_key,
    'HAS_CHILD_CAPABILITY' AS edge_type,
    'capability:' || parent_id AS source_key,
    'capability:' || id AS target_key,
    json_object('sort_order', sort_order) AS properties_json
FROM capability_nodes
WHERE parent_id IS NOT NULL AND status='active'
UNION ALL
SELECT
    'capability-relation:' || id, relation_type,
    'capability:' || source_capability_id,
    'capability:' || target_capability_id,
    json_object('weight',weight,'confidence',confidence,'review_status',review_status)
FROM capability_relations
UNION ALL
SELECT
    'career-capability:' || snapshot_id || ':' || job_id || ':' || capability_id,
    'REQUIRES_CAPABILITY',
    'career:' || job_id,
    'capability:' || capability_id,
    json_object(
        'importance',importance,'weight',weight,'confidence',confidence,
        'evidence_count',evidence_count,'review_status',review_status
    )
FROM job_capability_profiles
UNION ALL
SELECT
    'career-similarity:' || run_id || ':' || job_a_id || ':' || job_b_id,
    'SIMILAR_TO',
    'career:' || job_a_id,
    'career:' || job_b_id,
    json_object(
        'score',score_total,'cosine',capability_cosine,
        'jaccard',core_jaccard,'hierarchy',hierarchy_score,
        'shared_count',shared_capability_count,'review_status',review_status
    )
FROM job_similarities;
