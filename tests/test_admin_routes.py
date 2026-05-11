import io
import unittest

from werkzeug.security import generate_password_hash

from application import app
from connections import get_db_connection


class AdminRouteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()
        cls.db = get_db_connection()

    def setUp(self):
        self.admin_id, self.admin_username = self._create_user(role=9, prefix="admin")
        self.user_id, self.username = self._create_user(role=1, prefix="user")
        self.word_set_id = self._get_any_existing_set_id()

    def tearDown(self):
        self._delete_user(self.admin_id)
        self._delete_user(self.user_id)
        self.db.commit()

    def _create_user(self, role, prefix):
        username = f"{prefix}_{self._suffix()}"
        user_id = (
            self.db.execute(
                """
                INSERT INTO users(username, password, created_at, preferred_lang, learning_lang, roles)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """,
                (username, generate_password_hash("ValidPassword123!"), 1, 2, int(role)),
            )
        ).lastrowid
        self.db.commit()
        return int(user_id), username

    def _delete_user(self, user_id):
        self.db.execute("DELETE FROM users WHERE id = ?", (int(user_id),))

    def _suffix(self):
        return self.db.execute("SELECT hex(randomblob(4)) AS suffix").fetchone()["suffix"]

    def _get_any_existing_set_id(self):
        row = self.db.execute("SELECT id FROM word_sets ORDER BY id ASC LIMIT 1").fetchone()
        if row is None:
            self.fail("Expected at least one seeded word set for admin tests")
        return int(row["id"])

    def _get_word_type_id(self, type_name):
        row = self.db.execute("SELECT id FROM word_type WHERE type = ? LIMIT 1", (type_name,)).fetchone()
        if row is None:
            self.fail(f"Expected word_type entry for {type_name}")
        return int(row["id"])

    def _login_as(self, user_id, username):
        with self.client.session_transaction() as sess:
            sess["user_id"] = int(user_id)
            sess["username"] = username
            sess["language"] = {"charcode": "en", "dir": "ltr", "learning": 2, "preferred": 1}

    def _count_set_items(self, set_id):
        row = self.db.execute(
            "SELECT COUNT(*) AS count FROM set_item WHERE word_set_id = ?",
            (int(set_id),),
        ).fetchone()
        return int(row["count"])

    def _lemma_columns(self):
        rows = self.db.execute("PRAGMA table_info(lemma)").fetchall()
        return [row["name"] for row in rows]

    def _create_temp_lemma(self, value_suffix, language_id=1, pos_id=1, value_prefix="bulk"):
        lemma_id = self.db.execute(
            "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
            (int(language_id), int(pos_id), "", None),
        ).lastrowid
        self.db.execute(
            """
            INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (lemma_id, int(language_id), "surface", "Latn", f"{value_prefix}-{value_suffix}", f"{value_prefix}-{value_suffix}", 1),
        )
        self.db.execute(
            "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
            (lemma_id, int(pos_id), 1),
        )
        self.db.commit()
        return int(lemma_id)

    def _delete_temp_lemma(self, lemma_id):
        self.db.execute("DELETE FROM set_item WHERE sense_id IN (SELECT id FROM sense WHERE lemma_id = ?)", (int(lemma_id),))
        self.db.execute("DELETE FROM sense_translation WHERE source_sense_id IN (SELECT id FROM sense WHERE lemma_id = ?) OR target_sense_id IN (SELECT id FROM sense WHERE lemma_id = ?)", (int(lemma_id), int(lemma_id)))
        self.db.execute("DELETE FROM sense WHERE lemma_id = ?", (int(lemma_id),))
        self.db.execute("DELETE FROM lemma_form WHERE lemma_id = ?", (int(lemma_id),))
        self.db.execute("DELETE FROM lemma WHERE id = ?", (int(lemma_id),))
        self.db.commit()

    def test_admin_home_requires_admin(self):
        self._login_as(self.user_id, self.username)
        response = self.client.get("/admin/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.headers.get("Location", ""))

    def test_admin_home_renders_for_admin(self):
        self._login_as(self.admin_id, self.admin_username)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin", response.get_data(as_text=True))

    def test_admin_vocabulary_renders_for_admin(self):
        self._login_as(self.admin_id, self.admin_username)
        response = self.client.get("/admin/vocabulary/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Vocabulary", response.get_data(as_text=True))

    def test_admin_upload_page_renders_for_admin(self):
        self._login_as(self.admin_id, self.admin_username)
        response = self.client.get("/admin/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Upload Vocabulary", response.get_data(as_text=True))

    def test_admin_upload_post_adds_word(self):
        self._login_as(self.admin_id, self.admin_username)

        suffix = self._suffix()
        english_word = f"adminleaf_{suffix}"
        hebrew_word = f"עלה_{suffix}"

        csv_bytes = io.BytesIO(
            (
                "English,en_pronunciation,עברית,he_pronunciation,word_type\n"
                f"{english_word},leef,{hebrew_word},aleh,noun\n"
            ).encode("utf-8")
        )

        before_count = self._count_set_items(self.word_set_id)
        try:
            response = self.client.post(
                "/admin/upload/",
                data={
                    "word_set_id": str(self.word_set_id),
                    "additional_set": "---------",
                    "file": (csv_bytes, "admin-upload.csv"),
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
                self.db.execute(
                    "DELETE FROM sense_translation WHERE source_sense_id = ? OR target_sense_id = ?",
                    (int(row["sense_id"]), int(row["sense_id"])),
                )
                self.db.execute("DELETE FROM set_item WHERE sense_id = ?", (int(row["sense_id"]),))
                self.db.execute("DELETE FROM sense WHERE id = ?", (int(row["sense_id"]),))
                self.db.execute("DELETE FROM lemma_form WHERE lemma_id = ?", (int(row["lemma_id"]),))
                self.db.execute("DELETE FROM lemma WHERE id = ?", (int(row["lemma_id"]),))
            self.db.commit()

    def test_admin_vocabulary_bulk_archive_updates_state(self):
        self._login_as(self.admin_id, self.admin_username)

        lemma_columns = self._lemma_columns()
        if "state" not in lemma_columns:
            self.skipTest("lemma.state is not available in this schema")

        lemma_id = self._create_temp_lemma(self._suffix())
        try:
            response = self.client.post(
                "/admin/vocabulary/bulk-action/",
                data={
                    "action": "archive",
                    "lemma_ids": [str(lemma_id)],
                    "page": "1",
                    "per_page": "20",
                    "q": "",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/vocabulary/", response.headers.get("Location", ""))

            row = self.db.execute("SELECT state FROM lemma WHERE id = ?", (lemma_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual("archived", row["state"])
        finally:
            self._delete_temp_lemma(lemma_id)

    def test_admin_vocabulary_create_saves_vocalization_and_definition(self):
        self._login_as(self.admin_id, self.admin_username)

        lemma_value = f"create-primary-{self._suffix()}"
        vocalization = f"רָעֵב-{self._suffix()}"
        definition = f"definition-{self._suffix()}"
        lemma_id = None
        try:
            response = self.client.post(
                "/admin/vocabulary/create/",
                data={
                    "lemma_value": lemma_value,
                    "vocalization": vocalization,
                    "definition": definition,
                    "language_id": "2",
                    "pos_id": str(self._get_word_type_id("noun")),
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)

            location = response.headers.get("Location", "")
            self.assertIn("/admin/vocabulary/edit/", location)
            lemma_id = int(location.rstrip("/").split("/")[-1])

            sense_row = self.db.execute("SELECT gloss FROM sense WHERE lemma_id = ? AND is_primary = 1", (lemma_id,)).fetchone()
            self.assertIsNotNone(sense_row)
            self.assertEqual(definition, sense_row["gloss"])

            form_rows = self.db.execute(
                "SELECT value, is_primary FROM lemma_form WHERE lemma_id = ? ORDER BY is_primary DESC, id ASC",
                (lemma_id,),
            ).fetchall()
            self.assertEqual(lemma_value, form_rows[0]["value"])
            self.assertTrue(any(row["value"] == vocalization and int(row["is_primary"] or 0) == 0 for row in form_rows))
        finally:
            if lemma_id is not None:
                self._delete_temp_lemma(lemma_id)

    def test_admin_vocabulary_edit_updates_vocalization_and_definition(self):
        self._login_as(self.admin_id, self.admin_username)

        lemma_id = self._create_temp_lemma(self._suffix(), language_id=2, pos_id=self._get_word_type_id("noun"), value_prefix="edit-primary")
        try:
            response = self.client.post(
                f"/admin/vocabulary/edit/{lemma_id}/",
                data={
                    "lemma_value": f"edit-primary-updated-{self._suffix()}",
                    "vocalization": f"עָדְכָן-{self._suffix()}",
                    "definition": f"updated-definition-{self._suffix()}",
                    "pos_id": str(self._get_word_type_id("noun")),
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)

            sense_row = self.db.execute("SELECT gloss FROM sense WHERE lemma_id = ? AND is_primary = 1", (lemma_id,)).fetchone()
            self.assertIsNotNone(sense_row)
            self.assertIn("updated-definition-", sense_row["gloss"])

            primary_row = self.db.execute(
                "SELECT value FROM lemma_form WHERE lemma_id = ? AND is_primary = 1 LIMIT 1",
                (lemma_id,),
            ).fetchone()
            self.assertIsNotNone(primary_row)
            self.assertTrue(primary_row["value"].startswith("edit-primary-updated-"))

            vocalization_rows = self.db.execute(
                "SELECT value, is_primary FROM lemma_form WHERE lemma_id = ? AND is_primary = 0",
                (lemma_id,),
            ).fetchall()
            self.assertTrue(any(row["value"].startswith("עָדְכָן-") for row in vocalization_rows))
        finally:
            self._delete_temp_lemma(lemma_id)

    def test_admin_vocabulary_filters_by_language_pos_and_search(self):
        self._login_as(self.admin_id, self.admin_username)

        english_suffix = self._suffix()
        hebrew_suffix = self._suffix()
        english_value = f"filter-en-{english_suffix}"
        hebrew_value = f"filter-he-{hebrew_suffix}"

        lemma_en = self._create_temp_lemma(english_suffix, language_id=1, pos_id=1, value_prefix="filter-en")
        lemma_he = self._create_temp_lemma(hebrew_suffix, language_id=2, pos_id=2, value_prefix="filter-he")
        try:
            response = self.client.get(
                "/admin/vocabulary/?q=filter-&language_id=1&pos_id=1&sort=name-desc",
            )
            self.assertEqual(response.status_code, 200)

            body = response.get_data(as_text=True)
            self.assertIn(english_value, body)
            self.assertNotIn(hebrew_value, body)
        finally:
            self._delete_temp_lemma(lemma_en)
            self._delete_temp_lemma(lemma_he)


if __name__ == "__main__":
    unittest.main()
