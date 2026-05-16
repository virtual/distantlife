import unittest
from application import app
from connections import get_db_connection
from helpers import initialize_user_pet_unlocks
from werkzeug.security import generate_password_hash


class QuizSetInteractionTestCase(unittest.TestCase):
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
        username = f"quiz_user_{self.user_id_suffix()}"
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

    def _delete_user_data(self, user_id):
        self.db.execute("DELETE FROM users WHERE id = ?", (int(user_id),))

    def user_id_suffix(self):
        return self.db.execute("SELECT hex(randomblob(4)) AS suffix").fetchone()["suffix"]

    def test_quiz_post_and_experience_increment(self):
        # Find an existing word_set id
        row = self.db.execute("SELECT id FROM word_sets LIMIT 1").fetchone()
        if row is None:
            self.skipTest("No word_sets available in DB to run quiz integration test")
        set_id = int(row["id"])

        self._login()
        # Ensure user has an active pet (route requires adopted pet)
        self._create_active_pet(pet_type=10, name="Bramble")
        # Request initial quiz page (POST as per app flow to render options)
        resp = self.client.post("/quiz/set/", data={"set_id": set_id, "page": 0})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        # Ensure radio inputs exist by searching raw HTML for the radio name
        self.assertIn('name="wordchoice"', body)

        # Confirm there is at least one correct option present (data-type == 'success')
        self.assertIn('data-type="success"', body)

        # Simulate selecting the correct answer by posting with experience=1
        resp2 = self.client.post("/quiz/set/", data={"set_id": set_id, "page": 0, "experience": 1})
        self.assertEqual(resp2.status_code, 200)
        body2 = resp2.get_data(as_text=True)

        # The returned page should include the hidden experience input with the updated value
        self.assertIn('id="experience"', body2)
        self.assertIn('value="1"', body2)


if __name__ == '__main__':
    unittest.main()
