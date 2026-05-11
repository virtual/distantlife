import io
import unittest
import os
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from application import app
from connections import get_db_connection
from helpers import canonical_vocab_enabled, get_word_translation, resolve_canonical_sense_id


class CsvUploadTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()
        cls.db = get_db_connection()

    def setUp(self):
        self.user_id, self.username = self._create_admin_user()
        self.word_set_id = self._get_any_existing_set_id()

    def tearDown(self):
        self._delete_user(self.user_id)
        self.db.commit()

    def _create_admin_user(self):
        username = f"admin_upload_{self._user_suffix()}"
        user_id = (
            self.db.execute(
                """
                INSERT INTO users(username, password, created_at, preferred_lang, learning_lang, roles)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """,
                (username, generate_password_hash("ValidPassword123!"), 1, 2, 9),
            )
        ).lastrowid
        self.db.commit()
        return int(user_id), username

    def _delete_user(self, user_id):
        self.db.execute("DELETE FROM users WHERE id = ?", (int(user_id),))

    def _user_suffix(self):
        return self.db.execute("SELECT hex(randomblob(4)) AS suffix").fetchone()["suffix"]

    def _get_any_existing_set_id(self):
        row = self.db.execute("SELECT id FROM word_sets ORDER BY id ASC LIMIT 1").fetchone()
        if row is None:
            self.fail("Expected at least one seeded word set for upload tests")
        return int(row["id"])

    def _login_as_admin(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["username"] = self.username

    def _count_set_items(self, set_id):
        row = self.db.execute(
            "SELECT COUNT(*) AS count FROM set_item WHERE word_set_id = ?",
            (int(set_id),),
        ).fetchone()
        return int(row["count"])

    def test_uploadwordset_ignores_placeholder_additional_set(self):
        self._login_as_admin()
        suffix = self._user_suffix()
        english_word = f"leaf_{suffix}"
        hebrew_word = f"עָלֶה_{suffix}"

        # Create an in-memory CSV file. The tuple used in the POST below
        # is (fileobj, filename) where `filename` is the client-side name
        # sent in the multipart request. The test does not require an on-disk
        # file — `csv_bytes` is in-memory — but when the application saves
        # the uploaded file it will create a temporary file on disk using
        # the provided filename metadata.
        csv_bytes = io.BytesIO(
            (
                "English,en_pronunciation,עברית,he_pronunciation,word_type\n"
                f"{english_word},leef,{hebrew_word},aleh,noun\n"
            ).encode("utf-8")
        )

        before_count = self._count_set_items(self.word_set_id)
        try:
            # Post the in-memory CSV. The second item in the tuple below
            # is the filename metadata sent to the server.
            response = self.client.post(
                "/uploadwordset",
                data={
                    "word_set_id": str(self.word_set_id),
                    "additional_set": "---------",
                    "file": (csv_bytes, "הפאון הרעב וארוחת הצהריים שנעלמה.csv"),
                },
                content_type="multipart/form-data",
                follow_redirects=False,
            )

            self.assertEqual(response.status_code, 302)
            self.assertIn(f"/edit/set/?set_id={self.word_set_id}", response.headers.get("Location", ""))

            after_count = self._count_set_items(self.word_set_id)
            self.assertEqual(before_count + 1, after_count)
        finally:
            sense_rows = self.db.execute(
                """
                SELECT s.id AS sense_id, l.id AS lemma_id
                FROM sense s
                JOIN lemma l ON l.id = s.lemma_id
                JOIN lemma_form lf ON lf.lemma_id = l.id
                WHERE lf.value IN (?, ?)
                """,
                (english_word, hebrew_word),
            ).fetchall()
            for row in sense_rows:
                self.db.execute("DELETE FROM sense_translation WHERE source_sense_id = ? OR target_sense_id = ?", (int(row["sense_id"]), int(row["sense_id"])))
                self.db.execute("DELETE FROM set_item WHERE sense_id = ?", (int(row["sense_id"]),))
                self.db.execute("DELETE FROM sense WHERE id = ?", (int(row["sense_id"]),))
                self.db.execute("DELETE FROM lemma_form WHERE lemma_id = ?", (int(row["lemma_id"]),))
                self.db.execute("DELETE FROM lemma WHERE id = ?", (int(row["lemma_id"]),))
            self.db.commit()

    def test_legacy_word_id_resolves_to_canonical_sense_translation(self):
        source_legacy_word_id = int(self.db.execute("SELECT ABS(RANDOM()) % 100000000 AS value").fetchone()["value"]) + 500000

        source_lemma_id = self.db.execute(
            "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath, legacy_word_id) VALUES (?, ?, ?, ?, ?)",
            (1, 1, "", None, source_legacy_word_id),
        ).lastrowid
        source_sense_id = self.db.execute(
            "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
            (source_lemma_id, 1, 1),
        ).lastrowid
        self.db.execute(
            "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_lemma_id, 1, "surface", "Latn", "shim-source", "shim-source", 1),
        )

        target_lemma_id = self.db.execute(
            "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
            (2, 1, "", None),
        ).lastrowid
        target_sense_id = self.db.execute(
            "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
            (target_lemma_id, 1, 1),
        ).lastrowid
        self.db.execute(
            "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (target_lemma_id, 2, "surface", "Latn", "shim-target", "shim-target", 1),
        )
        self.db.execute(
            "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
            (source_sense_id, target_sense_id, "exact"),
        )
        self.db.commit()

        with app.test_request_context("/"):
            self.assertEqual(source_sense_id, resolve_canonical_sense_id(source_legacy_word_id))
            self.assertEqual(
                "shim-target",
                get_word_translation(source_legacy_word_id, orig_lang=2, trans_lang=1),
            )

        self.db.execute("DELETE FROM sense_translation WHERE source_sense_id = ? OR target_sense_id = ?", (source_sense_id, source_sense_id))
        self.db.execute("DELETE FROM sense_translation WHERE source_sense_id = ? OR target_sense_id = ?", (target_sense_id, target_sense_id))
        self.db.execute("DELETE FROM sense WHERE id = ?", (source_sense_id,))
        self.db.execute("DELETE FROM sense WHERE id = ?", (target_sense_id,))
        self.db.execute("DELETE FROM lemma_form WHERE lemma_id = ?", (source_lemma_id,))
        self.db.execute("DELETE FROM lemma_form WHERE lemma_id = ?", (target_lemma_id,))
        self.db.execute("DELETE FROM lemma WHERE id = ?", (source_lemma_id,))
        self.db.execute("DELETE FROM lemma WHERE id = ?", (target_lemma_id,))
        self.db.commit()

    def test_canonical_vocab_feature_flag_defaults_to_schema_presence(self):
        self.assertTrue(canonical_vocab_enabled())

    def test_canonical_vocab_feature_flag_respects_env_override(self):
        with patch.dict(os.environ, {"VOCAB_CANONICAL_ENABLED": "0"}, clear=False):
            self.assertFalse(canonical_vocab_enabled())

        with patch.dict(os.environ, {"VOCAB_CANONICAL_ENABLED": "true"}, clear=False):
            self.assertTrue(canonical_vocab_enabled())


if __name__ == "__main__":
    unittest.main()