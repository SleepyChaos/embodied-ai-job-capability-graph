-- Confidence gates, retry audit, and automatic governance decisions.

ALTER TABLE capability_extraction_runs
    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1 CHECK (attempt_count BETWEEN 1 AND 3);
ALTER TABLE capability_extraction_runs
    ADD COLUMN retry_reason TEXT;
ALTER TABLE capability_extraction_runs
    ADD COLUMN automated_decision_summary TEXT;

ALTER TABLE capability_mentions
    ADD COLUMN decision_mode TEXT NOT NULL DEFAULT 'manual_review'
    CHECK (decision_mode IN ('auto_alias','auto_merge','auto_create','manual_review'));

UPDATE capability_mentions
SET decision_mode = CASE
    WHEN normalization_status='exact_alias' THEN 'auto_alias'
    WHEN normalization_status='ai_equivalent' THEN 'auto_merge'
    ELSE 'manual_review'
END;

INSERT INTO schema_migrations(version,description,source_sha256)
VALUES ('009','能力抽取置信度门槛、自动决策与重做审计','manual-009-capability-confidence-automation');
