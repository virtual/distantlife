import unittest
from werkzeug.security import generate_password_hash

from application import app, _tokenize_sentence_text
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
            sess.clear() # Clear session to ensure a clean state for each test
            sess["user_id"] = self.user_id
            sess["username"] = self.username
            # Include learning_charcode so get_learning_language_charcode returns 'en'
            sess["language"] = {"charcode": "en", "dir": "ltr", "learning_charcode": "en"}

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
        self.assertIn("יום הגינון של פאון", body)

    def test_locked_quest_shows_available_tag_when_owned_pet_matches(self):
        self._login()
        self._create_active_pet(pet_type=2, name="Unicorn")
        self._add_owned_pet(pet_type=10, name="Bramble")

        response = self.client.get("/quests")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("יום הגינון של פאון", body)
        self.assertIn("Available if you switch to Faun", body)
        self.assertIn("quest-badge-available", body)

    def test_quest_page_redirects_without_active_pet(self):
        self._login()
        response = self.client.get("/quest/garden_adventure", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/adopt", response.headers.get("Location", ""))

    def test_quest_page_renders_with_active_pet(self):
        self._login()
        self._create_active_pet(pet_type=10, name="Bramble")
        response = self.client.get("/quest/garden_adventure")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("הסל הריק", body)
        self.assertIn("Bramble", body)

    def test_quiz_page_renders_step_wizard(self):
        self._login()
        self._create_active_pet(pet_type=10, name="Bramble")
        response = self.client.get("/quiz/garden_adventure/garden_adventure_ep1")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("quiz-step", body)
        self.assertTrue("data-order-builder" in body or "cloze-input" in body or "quiz-choice-group" in body)

    def test_sentence_builder_tokenizer_strips_punctuation(self):
        self.assertEqual(
            _tokenize_sentence_text("Hello, world! The basket."),
            ["Hello", "world", "The", "basket"],
        )

    def test_quiz_hint_and_retry_flow(self):
        self._login()
        self._create_active_pet(pet_type=10, name="Bramble")

        response = self.client.post(
            "/quiz/garden_adventure/garden_adventure_ep1/submit",
            data={
                "action": "submit",
                "answer_order": "1,0",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Review Context", body)

        hint_response = self.client.post(
            "/quiz/garden_adventure/garden_adventure_ep1/submit",
            data={"action": "hint"},
            follow_redirects=True,
        )
        self.assertEqual(hint_response.status_code, 200)
        hint_body = hint_response.get_data(as_text=True)
        self.assertIn("Correct answer", hint_body)
        self.assertIn("Retry", hint_body)

    def test_quiz_submission_reaches_summary_screen(self):
        self._login()
        self._create_active_pet(pet_type=10, name="Bramble")

        with self.client.session_transaction() as sess:
            sess["quiz_wizard:garden_adventure:garden_adventure_ep1"] = {
                "quest_id": "garden_adventure",
                "episode_id": "garden_adventure_ep1",
                "seed": 1,
                "current_step": 0,
                "score": 0,
                "finished": False,
                "recorded_completion": False,
                "started_at": "2026-05-29T00:00:00",
                "steps": [
                    {
                        "kind": "sentence",
                        "source_index": 0,
                        "sentence_id": "s1",
                        "sentence_text": "one two",
                        "sentence_tokens": [
                            {"index": 0, "text": "one"},
                            {"index": 1, "text": "two"},
                        ],
                        "shuffled_tokens": [
                            {"index": 1, "text": "two"},
                            {"index": 0, "text": "one"},
                        ],
                        "summary_prompt": "one two",
                        "correct_answer": "one two",
                        "correct_answer_translation": "uno dos",
                        "attempts": 0,
                        "awaiting_review": False,
                        "hint_revealed": False,
                        "completed": False,
                        "first_try_correct": False,
                        "earned_point": False,
                        "submitted_answer": "",
                        "step_number": 1,
                    }
                ],
            }

        response = self.client.post(
            "/quiz/garden_adventure/garden_adventure_ep1/submit",
            data={
                "action": "submit",
                "answer_order": "0,1",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Correct", body)
        self.assertIn("Translation", body)
        self.assertIn("Finish quiz", body)
        self.assertIn("uno dos", body)

        next_response = self.client.post(
            "/quiz/garden_adventure/garden_adventure_ep1/submit",
            data={"action": "next"},
            follow_redirects=True,
        )
        self.assertEqual(next_response.status_code, 200)
        next_body = next_response.get_data(as_text=True)
        self.assertIn("Quiz complete", next_body)
        self.assertIn("1 / 1 points", next_body)

    def test_quiz_forfeit_clears_state_and_restarts(self):
        self._login()
        self._create_active_pet(pet_type=10, name="Bramble")

        with self.client.session_transaction() as sess:
            sess["quiz_wizard:garden_adventure:garden_adventure_ep1"] = {
                "quest_id": "garden_adventure",
                "episode_id": "garden_adventure_ep1",
                "seed": 1,
                "current_step": 0,
                "score": 1,
                "finished": False,
                "recorded_completion": False,
                "started_at": "2026-05-29T00:00:00",
                "steps": [
                    {
                        "kind": "sentence",
                        "source_index": 0,
                        "sentence_id": "s1",
                        "sentence_text": "one two",
                        "sentence_tokens": [
                            {"index": 0, "text": "one"},
                            {"index": 1, "text": "two"},
                        ],
                        "shuffled_tokens": [
                            {"index": 1, "text": "two"},
                            {"index": 0, "text": "one"},
                        ],
                        "summary_prompt": "one two",
                        "correct_answer": "one two",
                        "attempts": 0,
                        "awaiting_review": False,
                        "hint_revealed": False,
                        "completed": False,
                        "first_try_correct": False,
                        "earned_point": False,
                        "submitted_answer": "",
                        "step_number": 1,
                    }
                ],
            }

        response = self.client.post(
            "/quiz/garden_adventure/garden_adventure_ep1/submit",
            data={"action": "forfeit"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("הסל הריק", body)
        self.assertIn("Bramble", body)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("quiz_wizard:garden_adventure:garden_adventure_ep1"))


if __name__ == "__main__":
    unittest.main()
