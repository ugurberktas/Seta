-- Migration 001: Review Decisions Table
-- Purpose: Persist passage-level human verification decisions (relevant/irrelevant)
-- Review Unit: (document_id, category, segment_id)
-- Note: 'unreviewed' status is represented by the absence of a row.

CREATE TABLE IF NOT EXISTS review_decisions (
    document_id TEXT NOT NULL,
    category TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('relevant', 'irrelevant')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (document_id, category, segment_id)
);

CREATE INDEX IF NOT EXISTS idx_review_decisions_doc
    ON review_decisions (document_id);

