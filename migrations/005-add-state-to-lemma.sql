-- Add state tracking to lemma for vocabulary approval workflow
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

ALTER TABLE lemma ADD COLUMN state TEXT NOT NULL DEFAULT 'published' CHECK (state IN ('draft', 'review', 'approved', 'published', 'archived'));
ALTER TABLE lemma ADD COLUMN archived_at TIMESTAMP;

-- Index for filtering by state
CREATE INDEX idx_lemma_state ON lemma(state);

COMMIT;
PRAGMA foreign_keys = ON;
