PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Preserve old tables for rollback window.
ALTER TABLE words RENAME TO words_old;
ALTER TABLE word_translation RENAME TO word_translation_old;
ALTER TABLE word_set_words RENAME TO word_set_words_old;

-- Core lexical model.
CREATE TABLE lemma (
    id INTEGER PRIMARY KEY,
    language_id INTEGER NOT NULL,
    pos_id INTEGER,
    pronunciation TEXT,
    audiopath TEXT,
    legacy_word_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lemma_form (
    id INTEGER PRIMARY KEY,
    lemma_id INTEGER NOT NULL,
    language_id INTEGER NOT NULL,
    form_type TEXT NOT NULL DEFAULT 'surface',
    script TEXT,
    value TEXT NOT NULL,
    search_key TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lemma_id, value)
);

CREATE TABLE sense (
    id INTEGER PRIMARY KEY,
    lemma_id INTEGER NOT NULL,
    gloss TEXT,
    part_of_speech INTEGER,
    is_primary INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sense_translation (
    id INTEGER PRIMARY KEY,
    source_sense_id INTEGER NOT NULL,
    target_sense_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'exact',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_sense_id, target_sense_id)
);

CREATE TABLE set_item (
    id INTEGER PRIMARY KEY,
    word_set_id INTEGER NOT NULL,
    sense_id INTEGER NOT NULL,
    prompt_mode TEXT NOT NULL DEFAULT 'show_all_forms',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word_set_id, sense_id)
);

-- Helpful indexes for query and search performance.
CREATE INDEX idx_lemma_language ON lemma(language_id);
CREATE INDEX idx_lemma_legacy_word ON lemma(legacy_word_id);
CREATE INDEX idx_lemma_form_lemma ON lemma_form(lemma_id);
CREATE INDEX idx_lemma_form_search ON lemma_form(search_key, language_id);
CREATE INDEX idx_sense_lemma ON sense(lemma_id);
CREATE INDEX idx_sense_translation_source ON sense_translation(source_sense_id);
CREATE INDEX idx_sense_translation_target ON sense_translation(target_sense_id);
CREATE INDEX idx_set_item_set ON set_item(word_set_id);

-- Backfill lemma and forms from old words.
INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath, legacy_word_id)
SELECT w.language_id, w.type, w.pronunciation, w.audiopath, w.id
FROM words_old w;

INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary)
SELECT l.id,
       l.language_id,
       'surface',
       CASE
         WHEN lower(lang.charcode) = 'he' THEN 'Hebr'
         ELSE 'Latn'
       END,
       COALESCE(w.wordstr, ''),
       lower(trim(COALESCE(w.wordstr, ''))),
       1
FROM lemma l
JOIN words_old w ON w.id = l.legacy_word_id
LEFT JOIN languages lang ON lang.id = l.language_id;

-- One primary sense per existing word as migration baseline.
INSERT INTO sense (lemma_id, gloss, part_of_speech, is_primary)
SELECT l.id, NULL, l.pos_id, 1
FROM lemma l;

-- Backfill sense-to-sense translations using legacy word mappings.
INSERT OR IGNORE INTO sense_translation (source_sense_id, target_sense_id, relation_type)
SELECT s_from.id,
       s_to.id,
       'exact'
FROM word_translation_old wt
JOIN lemma l_from ON l_from.legacy_word_id = wt.orig_word
JOIN lemma l_to ON l_to.legacy_word_id = wt.trans_word
JOIN sense s_from ON s_from.lemma_id = l_from.id AND s_from.is_primary = 1
JOIN sense s_to ON s_to.lemma_id = l_to.id AND s_to.is_primary = 1;

-- Backfill set membership to sense level.
INSERT OR IGNORE INTO set_item (word_set_id, sense_id, prompt_mode)
SELECT wsw.word_set_id,
       s.id,
       'show_all_forms'
FROM word_set_words_old wsw
JOIN lemma l ON l.legacy_word_id = wsw.word_id
JOIN sense s ON s.lemma_id = l.id AND s.is_primary = 1;

-- Preserve set naming while adding sense-aware linkage.
ALTER TABLE word_sets ADD COLUMN set_name_sense_id INTEGER;
UPDATE word_sets
SET set_name_sense_id = (
    SELECT s.id
    FROM lemma l
    JOIN sense s ON s.lemma_id = l.id AND s.is_primary = 1
    WHERE l.legacy_word_id = word_sets.set_name_word_id
    LIMIT 1
);

-- Keep legacy progress data and add sense-aware progress column.
ALTER TABLE words_learned ADD COLUMN sense_id INTEGER;
UPDATE words_learned
SET sense_id = (
    SELECT s.id
    FROM lemma l
    JOIN sense s ON s.lemma_id = l.id AND s.is_primary = 1
    WHERE l.legacy_word_id = words_learned.word
    LIMIT 1
);

COMMIT;
PRAGMA foreign_keys = ON;
