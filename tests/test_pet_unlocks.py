import unittest
import uuid

from flask import session
from werkzeug.security import generate_password_hash

from application import app
from connections import get_db_connection
from helpers import (
    STARTER_PET_TYPE_IDS,
    get_adoptable_pet_types_for_user,
    initialize_user_pet_unlocks,
)


class PetUnlockTestCase(unittest.TestCase):
    """Integration-style tests for user pet locking behavior."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()
        cls.db = get_db_connection()

    def setUp(self):
        self.user_id, self.username = self._create_normal_user()
        initialize_user_pet_unlocks(self.user_id)

    def tearDown(self):
        self._delete_user_and_related_data(self.user_id)
        self._reset_autoincrement_sequences()

    def _create_normal_user(self):
        username = f"test_user_{uuid.uuid4().hex[:12]}"
        row_id = (
            self.db.execute(
                """
                INSERT INTO users(username, password, created_at, preferred_lang, learning_lang, roles)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """,
                (username, generate_password_hash("ValidPassword123!"), 1, 2, 1),
            )
        ).lastrowid
        self.db.commit()
        return int(row_id), username

    def _delete_user_and_related_data(self, user_id):
        pet_rows = self.db.execute(
            "SELECT pet_id FROM owners WHERE owner_id = ?",
            (int(user_id),),
        ).fetchall()
        pet_ids = [int(row["pet_id"]) for row in pet_rows]

        self.db.execute("DELETE FROM owners WHERE owner_id = ?", (int(user_id),))
        self.db.execute("DELETE FROM user_pet_unlocks WHERE user_id = ?", (int(user_id),))
        self.db.execute("DELETE FROM users WHERE id = ?", (int(user_id),))

        for pet_id in pet_ids:
            still_owned = self.db.execute(
                "SELECT 1 FROM owners WHERE pet_id = ? LIMIT 1", (pet_id,)
            ).fetchone()
            if still_owned is None:
                self.db.execute("DELETE FROM pets WHERE id = ?", (pet_id,))

        self.db.commit()

    def _reset_autoincrement_sequences(self):
        """Reset AUTOINCREMENT counters for test-touched tables when supported."""
        seq_table = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
        ).fetchone()
        if seq_table is None:
            return

        # Only user_pet_unlocks is AUTOINCREMENT in this flow today.
        for table_name in ("user_pet_unlocks",):
            exists = self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if exists is None:
                continue

            max_row = self.db.execute(
                f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {table_name}"
            ).fetchone()
            self.db.execute(
                "UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
                (int(max_row["max_id"]), table_name),
            )

        self.db.commit()

    def _login_client_as_user(self, user_id, username):
        with self.client.session_transaction() as sess:
            sess["user_id"] = int(user_id)
            sess["username"] = username

    def test_initialize_user_pet_unlocks_assigns_starter_pets(self):
        unlocked_rows = self.db.execute(
            "SELECT pet_type_id FROM user_pet_unlocks WHERE user_id = ? ORDER BY pet_type_id",
            (self.user_id,),
        ).fetchall()
        unlocked_ids = [int(row["pet_type_id"]) for row in unlocked_rows]
        self.assertEqual(unlocked_ids, sorted(STARTER_PET_TYPE_IDS))

    def test_get_adoptable_pet_types_returns_only_unlocked_for_normal_user(self):
        with app.test_request_context("/adopt"):
            session["user_id"] = self.user_id
            session["username"] = self.username
            adoptable_rows = get_adoptable_pet_types_for_user(self.user_id)
        adoptable_ids = [int(row["id"]) for row in adoptable_rows]
        self.assertEqual(adoptable_ids, sorted(STARTER_PET_TYPE_IDS))

    def test_adopt_post_blocks_locked_pet_for_normal_user(self):
        self._login_client_as_user(self.user_id, self.username)

        response = self.client.post("/adopt", data={"pet_type": 2}, follow_redirects=False)

        self.assertEqual(response.status_code, 403)
        body = response.get_data(as_text=True)
        self.assertIn("pet type is locked", body)

    def test_adopt_post_allows_unlocked_pet_for_normal_user(self):
        self._login_client_as_user(self.user_id, self.username)

        response = self.client.post("/adopt", data={"pet_type": 1}, follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/pets", response.headers.get("Location", ""))

        owned = self.db.execute(
            """
            SELECT COUNT(*) AS count
            FROM owners o
            JOIN pets p ON p.id = o.pet_id
            WHERE o.owner_id = ? AND p.type = ?
            """,
            (self.user_id, 1),
        ).fetchone()
        self.assertGreaterEqual(int(owned["count"]), 1)


if __name__ == "__main__":
    unittest.main()
