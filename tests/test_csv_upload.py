import io
import unittest

from werkzeug.security import generate_password_hash

from application import app
from connections import get_db_connection


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


if __name__ == "__main__":
    unittest.main()