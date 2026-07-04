import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

import scripts.vocab_importer as vocab_importer


class VocabImporterTestCase(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self._create_schema()
        self._seed_languages()

    def tearDown(self):
        self.db.close()

    def _create_schema(self):
        self.db.executescript(
            """
            CREATE TABLE languages (
                id INTEGER PRIMARY KEY,
                charcode TEXT,
                dir TEXT,
                name TEXT,
                bodyclass TEXT
            );
            CREATE TABLE word_type (
                id INTEGER PRIMARY KEY,
                type TEXT
            );
            CREATE TABLE lemma (
                id INTEGER PRIMARY KEY,
                language_id INTEGER NOT NULL,
                pos_id INTEGER,
                pronunciation TEXT,
                audiopath TEXT,
                image_path TEXT,
                state TEXT,
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
            """
        )

    def _seed_languages(self):
        self.db.execute("INSERT INTO languages (id, charcode, dir, name) VALUES (1, 'he', 'rtl', 'Hebrew')")
        self.db.execute("INSERT INTO languages (id, charcode, dir, name) VALUES (2, 'en', 'ltr', 'English')")
        self.db.commit()

    def test_prepare_rows_fills_review_fields(self):
        original_loader = vocab_importer._load_wordfreq_candidates
        try:
            vocab_importer._load_wordfreq_candidates = lambda language_code, limit: [(1, "תפוח", 6.2)]
            rows = vocab_importer.prepare_rows(1, "he")
        finally:
            vocab_importer._load_wordfreq_candidates = original_loader

        self.assertEqual(1, len(rows))
        self.assertEqual("תפוח", rows[0]["hebrew_primary"])
        self.assertEqual("needs_translation", rows[0]["review_status"])

    def test_import_rows_creates_hebrew_forms_and_translation(self):
        rows = [
            {
                "hebrew_primary": "תפוח",
                "hebrew_vocalized": "תַּפּוּחַ",
                "english": "apple",
                "pos": "noun",
                "relation_type": "exact",
                "source": "dictionary",
                "confidence": "0.95",
                "review_status": "approved",
                "notes": "",
            }
        ]

        stats = vocab_importer.import_rows(self.db, rows)

        self.assertEqual(1, stats["pairs_imported"])
        lemma_rows = self.db.execute("SELECT id, language_id FROM lemma ORDER BY id ASC").fetchall()
        self.assertEqual(2, len(lemma_rows))

        he_form = self.db.execute(
            "SELECT value, search_key, is_primary FROM lemma_form WHERE language_id = 1 ORDER BY id ASC"
        ).fetchall()
        self.assertEqual("תפוח", he_form[0]["value"])
        self.assertEqual(1, he_form[0]["is_primary"])
        self.assertEqual("תַּפּוּחַ", he_form[1]["value"])
        self.assertEqual(0, he_form[1]["is_primary"])

        translation = self.db.execute("SELECT COUNT(*) AS count FROM sense_translation").fetchone()
        self.assertEqual(2, translation["count"])

        source_set = self.db.execute("SELECT COUNT(*) AS count FROM set_item").fetchone()
        self.assertEqual(0, source_set["count"])

    def test_import_rows_can_attach_to_set(self):
        rows = [
            {
                "hebrew_primary": "כלב",
                "english": "dog",
                "pos": "noun",
                "relation_type": "exact",
                "source": "dictionary",
                "confidence": "1.0",
                "review_status": "approved",
            }
        ]

        stats = vocab_importer.import_rows(self.db, rows, word_set_id=7)

        self.assertEqual(1, stats["pairs_imported"])
        set_item = self.db.execute("SELECT word_set_id, sense_id FROM set_item").fetchone()
        self.assertEqual(7, set_item["word_set_id"])


if __name__ == "__main__":
    unittest.main()