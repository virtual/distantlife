PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Canonical lifecycle metadata on lemma records.
ALTER TABLE lemma ADD COLUMN image_path TEXT;
ALTER TABLE lemma ADD COLUMN state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'review', 'approved', 'published', 'archived'));
ALTER TABLE lemma ADD COLUMN source_type TEXT NOT NULL DEFAULT 'manual' CHECK (source_type IN ('manual', 'csv-import', 'quest-generated', 'legacy-migration'));
ALTER TABLE lemma ADD COLUMN source_ref TEXT;
ALTER TABLE lemma ADD COLUMN created_by INTEGER;
ALTER TABLE lemma ADD COLUMN updated_by INTEGER;
ALTER TABLE lemma ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE lemma ADD COLUMN archived_at TIMESTAMP;

-- Existing migrated records should be treated as published baseline content.
UPDATE lemma
SET state = 'published',
    source_type = 'legacy-migration'
WHERE legacy_word_id IS NOT NULL;

-- Version history for rollback and audit.
CREATE TABLE lemma_version (
    id INTEGER PRIMARY KEY,
    lemma_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    state TEXT NOT NULL,
    changed_by INTEGER,
    change_note TEXT,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lemma_id, version_number),
    FOREIGN KEY (lemma_id) REFERENCES lemma(id)
);

-- Link quest episodes directly to canonical vocabulary IDs.
CREATE TABLE quest_episode_vocab (
    id INTEGER PRIMARY KEY,
    quest_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    lemma_id INTEGER NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'quest-generated', 'import')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quest_id, episode_id, lemma_id),
    FOREIGN KEY (lemma_id) REFERENCES lemma(id)
);

CREATE INDEX idx_lemma_state ON lemma(state);
CREATE INDEX idx_lemma_source_type ON lemma(source_type);
CREATE INDEX idx_lemma_updated_at ON lemma(updated_at);
CREATE INDEX idx_lemma_version_lemma ON lemma_version(lemma_id);
CREATE INDEX idx_qev_quest_episode ON quest_episode_vocab(quest_id, episode_id);
CREATE INDEX idx_qev_lemma ON quest_episode_vocab(lemma_id);

-- Keep updated_at fresh whenever a lemma row changes.
CREATE TRIGGER trg_lemma_touch_updated_at
AFTER UPDATE ON lemma
FOR EACH ROW
BEGIN
    UPDATE lemma
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

COMMIT;
PRAGMA foreign_keys = ON;
