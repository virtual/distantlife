import unittest
from werkzeug.security import generate_password_hash

from application import app
from connections import get_db_connection
from helpers import initialize_user_pet_unlocks


class QuestRouteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()
        cls.db = get_db_connection()

    def setUp(self):
        self.user_id, self.username = self._create_user()
        initialize_user_pet_unlocks(self.user_id)

    def tearDown(self):
        self._delete_user_data(self.user_id)
        self.db.commit()

    def _create_user(self):
        username = f"quest_user_{self.user_id_suffix()}"
        user_id = (
            self.db.execute(
                """
                INSERT INTO users(username, password, created_at, preferred_lang, learning_lang, roles)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                """,
                (username, generate_password_hash("ValidPassword123!"), 1, 2, 1),
            )
        ).lastrowid
        self.db.commit()
        return int(user_id), username

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["username"] = self.username
            sess["language"] = {"charcode": "en", "dir": "ltr"}

    def _create_active_pet(self, pet_type=10, name="QuestPet"):
        pet_id = (
            self.db.execute(
                "INSERT INTO pets(type, name, created, exp) VALUES (?, ?, CURRENT_TIMESTAMP, 0)",
                (pet_type, name),
            )
        ).lastrowid
        self.db.execute(
            "INSERT INTO owners(owner_id, pet_id) VALUES (?, ?)",
            (self.user_id, pet_id),
        )
        self.db.execute(
            "UPDATE users SET active_pet_id = ? WHERE id = ?",
            (pet_id, self.user_id),
        )
        self.db.commit()
        return int(pet_id)

    def _add_owned_pet(self, pet_type=10, name="QuestPet"):
        pet_id = (
            self.db.execute(
                "INSERT INTO pets(type, name, created, exp) VALUES (?, ?, CURRENT_TIMESTAMP, 0)",
                (pet_type, name),
            )
        ).lastrowid
        self.db.execute(
            "INSERT INTO owners(owner_id, pet_id) VALUES (?, ?)",
            (self.user_id, pet_id),
        )
        self.db.commit()
        return int(pet_id)

    def _delete_user_data(self, user_id):
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

    def user_id_suffix(self):
        return self.db.execute("SELECT hex(randomblob(4)) AS suffix").fetchone()["suffix"]

    def test_quests_page_renders_for_logged_in_user(self):
        self._login()
        response = self.client.get("/quests")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Quest Board", body)
        self.assertIn("Hungry Faun", body)
        self.assertIn("Three Heads", body)

    def test_locked_quest_shows_available_tag_when_owned_pet_matches(self):
        self._login()
        self._create_active_pet(pet_type=2, name="Unicorn")
        self._add_owned_pet(pet_type=10, name="Bramble")

        response = self.client.get("/quests")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Hungry Faun", body)
        self.assertIn("Available if you switch to Faun", body)
        self.assertIn("quest-badge-available", body)

    def test_quest_page_redirects_without_active_pet(self):
        self._login()
        response = self.client.get("/quest/hungry_faun_01", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/adopt", response.headers.get("Location", ""))

    def test_quest_page_renders_with_active_pet(self):
        self._login()
        self._create_active_pet(pet_type=10, name="Bramble")
        response = self.client.get("/quest/hungry_faun_01")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("The Hungry Faun and the Missing Lunch", body)
        self.assertIn("Bramble", body)


if __name__ == "__main__":
    unittest.main()
