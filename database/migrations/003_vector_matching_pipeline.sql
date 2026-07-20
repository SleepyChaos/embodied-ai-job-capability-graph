-- Vectorization, posting identity and human-reviewed career matching (v4).
-- Additive only: v3 tables remain untouched.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS job_postings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER REFERENCES data_sources(id) ON DELETE SET NULL,
    company_id          INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    external_job_id     TEXT NOT NULL,
    canonical_url       TEXT,
    current_raw_jd_id   INTEGER REFERENCES raw_jd_documents(id) ON DELETE SET NULL,
    duplicate_of_id     INTEGER REFERENCES job_postings(id) ON DELETE SET NULL,
    posting_status      TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (posting_status IN ('open','closed','unknown')),
    identity_method     TEXT NOT NULL
                        CHECK (identity_method IN ('source_external_id','source_url','legacy_id')),
    first_seen_at       TEXT,
    last_seen_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source_id, external_job_id),
    CHECK (duplicate_of_id IS NULL OR duplicate_of_id <> id)
);

CREATE TABLE IF NOT EXISTS job_posting_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    posting_id          INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    raw_jd_id           INTEGER NOT NULL UNIQUE REFERENCES raw_jd_documents(id) ON DELETE RESTRICT,
    version_no          INTEGER NOT NULL CHECK (version_no >= 1),
    content_hash        TEXT NOT NULL,
    change_type         TEXT NOT NULL DEFAULT 'initial'
                        CHECK (change_type IN ('initial','unchanged','content_changed','status_changed')),
    is_current          INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1)),
    observed_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (posting_id, version_no)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_job_posting_current_version
ON job_posting_versions(posting_id) WHERE is_current=1;

CREATE INDEX IF NOT EXISTS idx_job_posting_identity
ON job_postings(source_id, external_job_id, posting_status);

CREATE INDEX IF NOT EXISTS idx_job_posting_duplicate
ON job_postings(duplicate_of_id);

CREATE TABLE IF NOT EXISTS embedding_models (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    model_code          TEXT NOT NULL UNIQUE,
    provider            TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    model_revision      TEXT NOT NULL,
    dimensions          INTEGER NOT NULL CHECK (dimensions > 0),
    distance_metric     TEXT NOT NULL DEFAULT 'cosine' CHECK (distance_metric='cosine'),
    normalized          INTEGER NOT NULL DEFAULT 1 CHECK (normalized IN (0,1)),
    model_sha256        TEXT,
    status              TEXT NOT NULL DEFAULT 'configured'
                        CHECK (status IN ('configured','ready','unavailable','deprecated')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vectorization_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key     TEXT NOT NULL UNIQUE,
    source_type         TEXT NOT NULL
                        CHECK (source_type IN ('manual','raw_jd','batch','backfill')),
    raw_jd_id           INTEGER REFERENCES raw_jd_documents(id) ON DELETE SET NULL,
    batch_id            INTEGER REFERENCES ingestion_batches(id) ON DELETE SET NULL,
    model_id            INTEGER REFERENCES embedding_models(id) ON DELETE SET NULL,
    input_json          TEXT NOT NULL CHECK (json_valid(input_json)),
    input_text_hash     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','running','succeeded','partial','failed','cancelled')),
    semantic_available  INTEGER NOT NULL DEFAULT 0 CHECK (semantic_available IN (0,1)),
    capability_count    INTEGER NOT NULL DEFAULT 0 CHECK (capability_count >= 0),
    candidate_count     INTEGER NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    progress            REAL NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    warning_json        TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(warning_json)),
    error_message       TEXT,
    lease_owner         TEXT,
    lease_expires_at    TEXT,
    attempt_count       INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    started_at          TEXT,
    completed_at        TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_vectorization_run_queue
ON vectorization_runs(status, created_at);

CREATE TABLE IF NOT EXISTS jd_capability_mentions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_jd_id           INTEGER NOT NULL REFERENCES raw_jd_documents(id) ON DELETE CASCADE,
    capability_id       INTEGER NOT NULL REFERENCES capability_nodes(id) ON DELETE RESTRICT,
    evidence_role       TEXT NOT NULL
                        CHECK (evidence_role IN ('title','required','responsibility','preferred','body')),
    evidence_text       TEXT NOT NULL,
    extraction_method   TEXT NOT NULL
                        CHECK (extraction_method IN ('dictionary','semantic','manual')),
    role_weight         REAL NOT NULL CHECK (role_weight BETWEEN 0 AND 1),
    extraction_confidence REAL NOT NULL CHECK (extraction_confidence BETWEEN 0 AND 1),
    mapping_confidence  REAL NOT NULL CHECK (mapping_confidence BETWEEN 0 AND 1),
    evidence_weight     REAL NOT NULL CHECK (evidence_weight BETWEEN 0 AND 1),
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending','approved','rejected','needs_revision')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (raw_jd_id, capability_id, evidence_role, evidence_text)
);

CREATE INDEX IF NOT EXISTS idx_jd_capability_mentions_jd
ON jd_capability_mentions(raw_jd_id, evidence_weight DESC);

CREATE INDEX IF NOT EXISTS idx_jd_capability_mentions_capability
ON jd_capability_mentions(capability_id, review_status);

CREATE TABLE IF NOT EXISTS jd_embeddings (
    raw_jd_id           INTEGER NOT NULL REFERENCES raw_jd_documents(id) ON DELETE CASCADE,
    model_id            INTEGER NOT NULL REFERENCES embedding_models(id) ON DELETE RESTRICT,
    input_text_hash     TEXT NOT NULL,
    dimensions          INTEGER NOT NULL CHECK (dimensions > 0),
    vector_blob         BLOB,
    vector_norm         REAL,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','ready','failed','stale')),
    error_message       TEXT,
    computed_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (raw_jd_id, model_id, input_text_hash),
    CHECK ((status='ready' AND vector_blob IS NOT NULL AND vector_norm IS NOT NULL)
        OR status<>'ready')
);

CREATE TABLE IF NOT EXISTS career_embeddings (
    snapshot_id         INTEGER NOT NULL REFERENCES graph_snapshots(id) ON DELETE CASCADE,
    job_id              INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    model_id            INTEGER NOT NULL REFERENCES embedding_models(id) ON DELETE RESTRICT,
    dimensions          INTEGER NOT NULL CHECK (dimensions > 0),
    vector_blob         BLOB NOT NULL,
    vector_norm         REAL NOT NULL,
    source_jd_count     INTEGER NOT NULL CHECK (source_jd_count >= 1),
    calculation_version TEXT NOT NULL,
    computed_at         TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, job_id, model_id)
);

CREATE TABLE IF NOT EXISTS job_match_candidates (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  INTEGER NOT NULL REFERENCES vectorization_runs(id) ON DELETE CASCADE,
    candidate_job_id        INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
    rank_no                 INTEGER NOT NULL CHECK (rank_no >= 1),
    suggestion              TEXT NOT NULL
                            CHECK (suggestion IN ('POSTING_VERSION','EXACT_DUPLICATE','SAME_CAREER','RELATED_CAREER','NEW_CAREER_CANDIDATE','INSUFFICIENT_EVIDENCE')),
    score_total             REAL NOT NULL CHECK (score_total BETWEEN 0 AND 1),
    capability_score        REAL NOT NULL CHECK (capability_score BETWEEN 0 AND 1),
    capability_l3_cosine    REAL NOT NULL CHECK (capability_l3_cosine BETWEEN 0 AND 1),
    capability_l2_cosine    REAL NOT NULL CHECK (capability_l2_cosine BETWEEN 0 AND 1),
    capability_l1_cosine    REAL NOT NULL CHECK (capability_l1_cosine BETWEEN 0 AND 1),
    semantic_score          REAL CHECK (semantic_score BETWEEN 0 AND 1),
    core_jaccard            REAL NOT NULL CHECK (core_jaccard BETWEEN 0 AND 1),
    title_score             REAL NOT NULL CHECK (title_score BETWEEN 0 AND 1),
    compatibility_score     REAL NOT NULL CHECK (compatibility_score BETWEEN 0 AND 1),
    coverage                REAL NOT NULL CHECK (coverage BETWEEN 0 AND 1),
    shared_capability_count INTEGER NOT NULL DEFAULT 0 CHECK (shared_capability_count >= 0),
    threshold_version       TEXT NOT NULL DEFAULT 'match-threshold-v1',
    explanation_json        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(explanation_json)),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id, candidate_job_id),
    UNIQUE (run_id, rank_no)
);

CREATE INDEX IF NOT EXISTS idx_job_match_run_rank
ON job_match_candidates(run_id, rank_no);

CREATE TABLE IF NOT EXISTS job_match_decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES vectorization_runs(id) ON DELETE CASCADE,
    candidate_id        INTEGER REFERENCES job_match_candidates(id) ON DELETE SET NULL,
    decision            TEXT NOT NULL
                        CHECK (decision IN ('POSTING_VERSION','EXACT_DUPLICATE','SAME_CAREER','RELATED_CAREER','NEW_CAREER_CANDIDATE','INSUFFICIENT_EVIDENCE','REJECT')),
    target_job_id       INTEGER REFERENCES job_positions(id) ON DELETE SET NULL,
    created_job_id      INTEGER REFERENCES job_positions(id) ON DELETE SET NULL,
    reviewer            TEXT NOT NULL,
    review_note         TEXT,
    applied             INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0,1)),
    applied_at          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id)
);

CREATE TABLE IF NOT EXISTS capability_candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_jd_id           INTEGER REFERENCES raw_jd_documents(id) ON DELETE SET NULL,
    run_id              INTEGER REFERENCES vectorization_runs(id) ON DELETE SET NULL,
    candidate_name      TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,
    suggested_parent_id INTEGER REFERENCES capability_nodes(id) ON DELETE SET NULL,
    source_text         TEXT NOT NULL,
    confidence          REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','needs_revision')),
    reviewed_capability_id INTEGER REFERENCES capability_nodes(id) ON DELETE SET NULL,
    reviewer            TEXT,
    review_note         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at         TEXT,
    UNIQUE (run_id, normalized_name, source_text)
);

CREATE TABLE IF NOT EXISTS job_similarity_components (
    run_id                  INTEGER NOT NULL,
    job_a_id                INTEGER NOT NULL,
    job_b_id                INTEGER NOT NULL,
    semantic_score          REAL CHECK (semantic_score BETWEEN 0 AND 1),
    title_score             REAL NOT NULL CHECK (title_score BETWEEN 0 AND 1),
    compatibility_score     REAL NOT NULL CHECK (compatibility_score BETWEEN 0 AND 1),
    threshold_version       TEXT NOT NULL,
    decision_band           TEXT NOT NULL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, job_a_id, job_b_id),
    FOREIGN KEY (run_id, job_a_id, job_b_id)
      REFERENCES job_similarities(run_id, job_a_id, job_b_id) ON DELETE CASCADE
);

CREATE VIEW IF NOT EXISTS v_vectorization_run_summary AS
SELECT
    r.id, r.source_type, r.raw_jd_id, r.batch_id, r.status,
    r.semantic_available, r.capability_count, r.candidate_count,
    r.progress, r.warning_json, r.error_message,
    r.created_at, r.started_at, r.completed_at,
    m.model_code, m.model_name, m.model_revision, m.dimensions,
    (SELECT MAX(score_total) FROM job_match_candidates c WHERE c.run_id=r.id) AS best_score,
    (SELECT suggestion FROM job_match_candidates c WHERE c.run_id=r.id ORDER BY rank_no LIMIT 1) AS best_suggestion
FROM vectorization_runs r
LEFT JOIN embedding_models m ON m.id=r.model_id;

CREATE TRIGGER IF NOT EXISTS trg_job_posting_duplicate_cycle_insert
BEFORE INSERT ON job_postings
WHEN NEW.duplicate_of_id IS NOT NULL
 AND EXISTS (SELECT 1 FROM job_postings p WHERE p.id=NEW.duplicate_of_id AND p.duplicate_of_id=NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'job posting duplicate cycle detected');
END;
