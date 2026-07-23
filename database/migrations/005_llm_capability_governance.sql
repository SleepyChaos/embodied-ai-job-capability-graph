-- LLM capability extraction, semantic normalization, and review workflow.

ALTER TABLE capabilities ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','merged','retired'));
ALTER TABLE capabilities ADD COLUMN review_status TEXT NOT NULL DEFAULT 'approved'
    CHECK (review_status IN ('pending','approved','rejected'));
ALTER TABLE capabilities ADD COLUMN source TEXT NOT NULL DEFAULT 'legacy_import';
ALTER TABLE capabilities ADD COLUMN merged_into_id INTEGER REFERENCES capabilities(id);

CREATE TABLE capability_extraction_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    career_unit_id      INTEGER NOT NULL REFERENCES career_units(id) ON DELETE CASCADE,
    input_hash          TEXT NOT NULL,
    model               TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','completed','completed_with_review','failed')),
    raw_response_json   TEXT,
    error_message       TEXT,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    started_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT,
    UNIQUE(career_unit_id, input_hash, model, prompt_version)
);

CREATE INDEX idx_capability_extraction_runs_unit
    ON capability_extraction_runs(career_unit_id);

CREATE TABLE capability_category_candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    direction_id        INTEGER NOT NULL REFERENCES capability_directions(id),
    proposed_name       TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,
    proposed_description TEXT,
    source_run_id       INTEGER NOT NULL REFERENCES capability_extraction_runs(id) ON DELETE CASCADE,
    confidence          REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','merged','rejected')),
    resolved_category_id INTEGER REFERENCES capability_categories(id),
    review_note         TEXT,
    reviewed_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(direction_id, normalized_name, status)
);

CREATE TABLE capability_candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id         INTEGER REFERENCES capability_categories(id),
    category_candidate_id INTEGER REFERENCES capability_category_candidates(id),
    proposed_name       TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,
    description         TEXT NOT NULL,
    source_run_id       INTEGER NOT NULL REFERENCES capability_extraction_runs(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','merged','rejected')),
    resolved_capability_id INTEGER REFERENCES capabilities(id),
    review_note         TEXT,
    reviewed_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (category_id IS NOT NULL OR category_candidate_id IS NOT NULL)
);

CREATE INDEX idx_capability_candidates_status
    ON capability_candidates(status);
CREATE INDEX idx_capability_candidates_normalized
    ON capability_candidates(normalized_name);

CREATE TABLE capability_mentions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES capability_extraction_runs(id) ON DELETE CASCADE,
    career_unit_id          INTEGER NOT NULL REFERENCES career_units(id) ON DELETE CASCADE,
    surface_name            TEXT NOT NULL,
    proposed_canonical_name TEXT NOT NULL,
    description             TEXT NOT NULL,
    level1_code             TEXT NOT NULL,
    level2_selection        TEXT NOT NULL CHECK (level2_selection IN ('existing','proposed')),
    level2_code             TEXT,
    level2_name             TEXT NOT NULL,
    requirement_level       TEXT NOT NULL
                            CHECK (requirement_level IN ('required','preferred','responsibility','mentioned')),
    evidence_text           TEXT NOT NULL,
    evidence_section        TEXT NOT NULL
                            CHECK (evidence_section IN ('title','responsibilities','requirements','preferred','body')),
    extraction_confidence   REAL NOT NULL CHECK (extraction_confidence BETWEEN 0 AND 1),
    classification_confidence REAL NOT NULL CHECK (classification_confidence BETWEEN 0 AND 1),
    normalization_status    TEXT NOT NULL
                            CHECK (normalization_status IN ('exact_alias','ai_equivalent','candidate','review')),
    matched_capability_id   INTEGER REFERENCES capabilities(id),
    capability_candidate_id INTEGER REFERENCES capability_candidates(id),
    category_candidate_id   INTEGER REFERENCES capability_category_candidates(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_capability_mentions_unit ON capability_mentions(career_unit_id);
CREATE INDEX idx_capability_mentions_run ON capability_mentions(run_id);

CREATE TABLE capability_normalization_reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mention_id          INTEGER NOT NULL REFERENCES capability_mentions(id) ON DELETE CASCADE,
    candidate_capability_id INTEGER REFERENCES capabilities(id),
    relation            TEXT NOT NULL
                        CHECK (relation IN ('same','broader','narrower','related','different','uncertain')),
    confidence          REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    reasoning           TEXT,
    model               TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected')),
    reviewed_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_capability_normalization_reviews_status
    ON capability_normalization_reviews(status);

INSERT INTO schema_migrations(version, description, source_sha256)
VALUES ('005', 'LLM能力抽取、语义归一化与审核治理', 'manual-005-llm-capability-governance');
