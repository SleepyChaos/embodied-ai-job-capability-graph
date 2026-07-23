-- Audit trail for the initial pending-candidate semantic grouping pass.

CREATE TABLE IF NOT EXISTS capability_bootstrap_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    model               TEXT NOT NULL,
    candidate_count     INTEGER NOT NULL,
    group_count         INTEGER,
    raw_response_json   TEXT NOT NULL,
    status              TEXT NOT NULL
                        CHECK (status IN ('planned','completed','failed')),
    error_message       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT
);

INSERT INTO schema_migrations(version, description, source_sha256)
VALUES ('007', '首批能力候选批内语义分组审计',
        'manual-007-capability-bootstrap-audit');
