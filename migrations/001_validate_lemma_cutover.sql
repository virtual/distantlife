-- Basic row-count checks.
SELECT (SELECT COUNT(*) FROM words_old) AS old_words,
       (SELECT COUNT(*) FROM lemma) AS lemma_count,
       (SELECT COUNT(*) FROM sense WHERE is_primary = 1) AS primary_sense_count;

SELECT (SELECT COUNT(*) FROM word_translation_old) AS old_translation_rows,
       (SELECT COUNT(*) FROM sense_translation) AS sense_translation_rows;

SELECT (SELECT COUNT(*) FROM word_set_words_old) AS old_set_rows,
       (SELECT COUNT(*) FROM set_item) AS set_item_rows;

-- Integrity checks.
SELECT COUNT(*) AS orphan_lemma_forms
FROM lemma_form lf
LEFT JOIN lemma l ON l.id = lf.lemma_id
WHERE l.id IS NULL;

SELECT COUNT(*) AS orphan_senses
FROM sense s
LEFT JOIN lemma l ON l.id = s.lemma_id
WHERE l.id IS NULL;

SELECT COUNT(*) AS orphan_set_items
FROM set_item si
LEFT JOIN sense s ON s.id = si.sense_id
WHERE s.id IS NULL;

SELECT COUNT(*) AS words_learned_without_sense
FROM words_learned
WHERE word IS NOT NULL AND sense_id IS NULL;

-- Potential duplicates in canonical search keys.
SELECT lf.language_id, lf.search_key, COUNT(*) AS duplicate_count
FROM lemma_form lf
WHERE lf.is_primary = 1
GROUP BY lf.language_id, lf.search_key
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, lf.search_key ASC;
