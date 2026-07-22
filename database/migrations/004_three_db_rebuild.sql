-- Embodied AI jobs database v5: Three-database rebuild.
-- Drops all legacy tables and creates new schema:
--   Part 1: Career Database (directions → sub_directions → units)
--   Part 2: Capability Database (directions → categories → capabilities → aliases)
--   Part 3: Enterprise Database (companies)

PRAGMA foreign_keys = OFF;

-- ============================================================
-- Drop all legacy tables and views
-- ============================================================

DROP VIEW IF EXISTS v_job_skill_current;
DROP VIEW IF EXISTS v_graph_nodes;
DROP VIEW IF EXISTS v_graph_edges;
DROP VIEW IF EXISTS v_job_skill_evidence_detail;
DROP VIEW IF EXISTS v_vectorization_run_summary;

DROP TABLE IF EXISTS job_match_decisions;
DROP TABLE IF EXISTS job_match_candidates;
DROP TABLE IF EXISTS jd_capability_mentions;
DROP TABLE IF EXISTS vectorization_runs;
DROP TABLE IF EXISTS embedding_models;
DROP TABLE IF EXISTS job_posting_versions;
DROP TABLE IF EXISTS job_postings;

DROP TABLE IF EXISTS capability_candidates;
DROP TABLE IF EXISTS graph_layout_cache;
DROP TABLE IF EXISTS graph_sync_runs;
DROP TABLE IF EXISTS graph_snapshots;
DROP TABLE IF EXISTS career_embeddings;
DROP TABLE IF EXISTS career_communities;
DROP TABLE IF EXISTS job_similarity_components;
DROP TABLE IF EXISTS job_similarities;
DROP TABLE IF EXISTS job_similarity_runs;
DROP TABLE IF EXISTS job_capability_profiles;

DROP TABLE IF EXISTS skill_capability_mappings;
DROP TABLE IF EXISTS capability_relations;
DROP TABLE IF EXISTS capability_aliases;
DROP TABLE IF EXISTS capability_nodes;
DROP TABLE IF EXISTS ontology_versions;

DROP TABLE IF EXISTS jd_company_links;
DROP TABLE IF EXISTS job_category_memberships;
DROP TABLE IF EXISTS job_categories;
DROP TABLE IF EXISTS skill_category_memberships;
DROP TABLE IF EXISTS skill_categories;
DROP TABLE IF EXISTS jd_batch_memberships;
DROP TABLE IF EXISTS ingestion_batches;

DROP TABLE IF EXISTS job_skill_evidence;
DROP TABLE IF EXISTS job_skill_mapping;
DROP TABLE IF EXISTS raw_jd_documents;
DROP TABLE IF EXISTS data_sources;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS job_positions;
DROP TABLE IF EXISTS job_aliases;

DROP TABLE IF EXISTS career_aliases_v3;
DROP TABLE IF EXISTS change_events;
DROP TABLE IF EXISTS graph_snapshot_job_skills;
DROP TABLE IF EXISTS jd_embeddings;
DROP TABLE IF EXISTS job_definition_versions;
DROP TABLE IF EXISTS job_similarity_explanations;
DROP TABLE IF EXISTS manual_review_tasks;
DROP TABLE IF EXISTS skill_definition_versions;
DROP TABLE IF EXISTS skill_taxonomy;

DROP TABLE IF EXISTS companies;
DROP TABLE IF EXISTS schema_migrations;

-- ============================================================
-- Recreate schema_migrations
-- ============================================================

CREATE TABLE schema_migrations (
    version         TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    source_sha256   TEXT NOT NULL,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Part 1: Career Database
-- ============================================================

-- 6 major career directions
CREATE TABLE career_directions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sub-directions (e.g., 4.1, 4.2, 4.3)
CREATE TABLE career_sub_directions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    direction_id    INTEGER NOT NULL REFERENCES career_directions(id) ON DELETE CASCADE,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_career_sub_directions_direction ON career_sub_directions(direction_id);

-- Career units (= JD entries from XLSX)
CREATE TABLE career_units (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_direction_id        INTEGER REFERENCES career_sub_directions(id),
    company_id              INTEGER REFERENCES companies(id),
    job_title               TEXT NOT NULL,
    city                    TEXT,
    salary                  TEXT,
    experience              TEXT,
    education               TEXT,
    url                     TEXT,
    jd_description          TEXT,
    other_info              TEXT,
    data_source             TEXT,
    source_platform         TEXT,
    collected_at            TEXT,
    semantic_vector         BLOB,
    capability_requirements TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_career_units_sub_direction ON career_units(sub_direction_id);
CREATE INDEX idx_career_units_company ON career_units(company_id);

-- ============================================================
-- Part 2: Capability Database
-- ============================================================

-- 6 major capability directions
CREATE TABLE capability_directions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Capability categories (second level)
CREATE TABLE capability_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    direction_id    INTEGER NOT NULL REFERENCES capability_directions(id) ON DELETE CASCADE,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_capability_categories_direction ON capability_categories(direction_id);

-- Capabilities (bottom level)
CREATE TABLE capabilities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES capability_categories(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    code            TEXT,
    description     TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_capabilities_category ON capabilities(category_id);
CREATE INDEX idx_capabilities_name ON capabilities(name);

-- Capability aliases (synonyms, abbreviations, translations)
CREATE TABLE capability_aliases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id       INTEGER NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    alias_name          TEXT NOT NULL,
    normalized_alias    TEXT NOT NULL,
    alias_type          TEXT NOT NULL DEFAULT 'synonym'
                        CHECK (alias_type IN ('synonym','abbreviation','translation','spelling_variant','custom')),
    confidence          REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_capability_aliases_capability ON capability_aliases(capability_id);
CREATE INDEX idx_capability_aliases_normalized ON capability_aliases(normalized_alias);

-- ============================================================
-- Part 3: Enterprise Database
-- ============================================================

CREATE TABLE companies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    normalized_name     TEXT NOT NULL UNIQUE,
    display_name        TEXT,
    website             TEXT,
    liepin_url          TEXT,
    description         TEXT,
    industry            TEXT,
    scale               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Cross-database: Job-Capability Links (many-to-many)
-- ============================================================

CREATE TABLE job_capability_links (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    career_unit_id      INTEGER NOT NULL REFERENCES career_units(id) ON DELETE CASCADE,
    capability_alias_id INTEGER NOT NULL REFERENCES capability_aliases(id) ON DELETE CASCADE,
    extraction_method   TEXT NOT NULL DEFAULT 'dictionary'
                        CHECK (extraction_method IN ('dictionary','vector_similarity','manual','llm')),
    confidence          REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    evidence_text       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(career_unit_id, capability_alias_id)
);

CREATE INDEX idx_job_capability_links_unit ON job_capability_links(career_unit_id);
CREATE INDEX idx_job_capability_links_alias ON job_capability_links(capability_alias_id);

-- ============================================================
-- Import tracking
-- ============================================================

CREATE TABLE import_batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_code      TEXT NOT NULL UNIQUE,
    source_file     TEXT,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    total_count     INTEGER NOT NULL DEFAULT 0,
    success_count   INTEGER NOT NULL DEFAULT 0,
    skip_count      INTEGER NOT NULL DEFAULT 0,
    fail_count      INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','completed','failed')),
    error_details   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Record migration
-- ============================================================

INSERT INTO schema_migrations (version, description, source_sha256)
VALUES ('004', 'Three-database rebuild: career/capability/enterprise', 'manual');

PRAGMA foreign_keys = ON;
