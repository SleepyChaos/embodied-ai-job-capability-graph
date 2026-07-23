-- Preserve every grounded JD quote returned during LLM capability extraction.
-- capability_mentions.evidence_text remains the primary quote for compatibility.

CREATE TABLE capability_mention_evidence (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mention_id          INTEGER NOT NULL REFERENCES capability_mentions(id) ON DELETE CASCADE,
    career_unit_id      INTEGER NOT NULL REFERENCES career_units(id) ON DELETE CASCADE,
    evidence_text       TEXT NOT NULL CHECK (length(trim(evidence_text)) > 0),
    evidence_section    TEXT NOT NULL
                        CHECK (evidence_section IN ('title','responsibilities','requirements','preferred','body')),
    source_field        TEXT NOT NULL
                        CHECK (source_field IN ('job_title','jd_description','other_info','combined_text')),
    start_offset        INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset          INTEGER NOT NULL CHECK (end_offset > start_offset),
    ordinal             INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    is_primary          INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
    source_hash         TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(mention_id,evidence_text,evidence_section,source_field,start_offset)
);

CREATE INDEX idx_capability_mention_evidence_mention
    ON capability_mention_evidence(mention_id,ordinal);
CREATE INDEX idx_capability_mention_evidence_unit
    ON capability_mention_evidence(career_unit_id);

-- Backfill the primary evidence already stored by migration 005.
INSERT OR IGNORE INTO capability_mention_evidence(
    mention_id,career_unit_id,evidence_text,evidence_section,source_field,
    start_offset,end_offset,ordinal,is_primary,source_hash
)
SELECT
    m.id,
    m.career_unit_id,
    m.evidence_text,
    m.evidence_section,
    CASE
      WHEN instr(COALESCE(cu.job_title,''),m.evidence_text) > 0 THEN 'job_title'
      WHEN instr(COALESCE(cu.jd_description,''),m.evidence_text) > 0 THEN 'jd_description'
      WHEN instr(COALESCE(cu.other_info,''),m.evidence_text) > 0 THEN 'other_info'
      ELSE 'combined_text'
    END,
    CASE
      WHEN instr(COALESCE(cu.job_title,''),m.evidence_text) > 0
        THEN instr(COALESCE(cu.job_title,''),m.evidence_text)-1
      WHEN instr(COALESCE(cu.jd_description,''),m.evidence_text) > 0
        THEN instr(COALESCE(cu.jd_description,''),m.evidence_text)-1
      WHEN instr(COALESCE(cu.other_info,''),m.evidence_text) > 0
        THEN instr(COALESCE(cu.other_info,''),m.evidence_text)-1
      ELSE instr(
        '岗位名称：' || COALESCE(cu.job_title,'') || char(10) ||
        'JD描述：' || COALESCE(cu.jd_description,'') || char(10) ||
        '其他信息：' || COALESCE(cu.other_info,''),
        m.evidence_text
      )-1
    END,
    CASE
      WHEN instr(COALESCE(cu.job_title,''),m.evidence_text) > 0
        THEN instr(COALESCE(cu.job_title,''),m.evidence_text)-1+length(m.evidence_text)
      WHEN instr(COALESCE(cu.jd_description,''),m.evidence_text) > 0
        THEN instr(COALESCE(cu.jd_description,''),m.evidence_text)-1+length(m.evidence_text)
      WHEN instr(COALESCE(cu.other_info,''),m.evidence_text) > 0
        THEN instr(COALESCE(cu.other_info,''),m.evidence_text)-1+length(m.evidence_text)
      ELSE instr(
        '岗位名称：' || COALESCE(cu.job_title,'') || char(10) ||
        'JD描述：' || COALESCE(cu.jd_description,'') || char(10) ||
        '其他信息：' || COALESCE(cu.other_info,''),
        m.evidence_text
      )-1+length(m.evidence_text)
    END,
    0,
    1,
    lower(hex(m.evidence_text))
FROM capability_mentions m
JOIN career_units cu ON cu.id=m.career_unit_id
WHERE length(trim(COALESCE(m.evidence_text,''))) > 0
  AND (
    instr(COALESCE(cu.job_title,''),m.evidence_text) > 0 OR
    instr(COALESCE(cu.jd_description,''),m.evidence_text) > 0 OR
    instr(COALESCE(cu.other_info,''),m.evidence_text) > 0 OR
    instr(
      '岗位名称：' || COALESCE(cu.job_title,'') || char(10) ||
      'JD描述：' || COALESCE(cu.jd_description,'') || char(10) ||
      '其他信息：' || COALESCE(cu.other_info,''),
      m.evidence_text
    ) > 0
  );

INSERT INTO schema_migrations(version,description,source_sha256)
VALUES ('008','LLM能力别称多条JD原文证据与字符定位','manual-008-capability-evidence-details');
