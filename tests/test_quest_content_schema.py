import unittest
from pathlib import Path

from quest_content import load_quest_content, validate_quest_file


class QuestContentSchemaTestCase(unittest.TestCase):
    """Validation tests for JSON-based quest content."""

    def test_hungry_faun_file_validates(self):
        errors = validate_quest_file(Path("quests/en/hungry_faun_01.json"))
        self.assertEqual([], errors, f"hungry_faun_01 has schema errors: {errors}")

    def test_counting_cerberus_file_validates(self):
        errors = validate_quest_file(Path("quests/en/counting_cerberus_01.json"))
        self.assertEqual([], errors, f"counting_cerberus_01 has schema errors: {errors}")

    def test_hungry_faun_hebrew_file_validates(self):
        errors = validate_quest_file(Path("quests/he/hungry_faun_01.json"))
        self.assertEqual([], errors, f"hungry_faun_01 (he) has schema errors: {errors}")

    def test_counting_cerberus_hebrew_file_validates(self):
        errors = validate_quest_file(Path("quests/he/counting_cerberus_01.json"))
        self.assertEqual([], errors, f"counting_cerberus_01 (he) has schema errors: {errors}")

    def test_pet_restrictions_are_present(self):
        hungry_faun = load_quest_content("hungry_faun_01", locale="en")
        counting_cerberus = load_quest_content("counting_cerberus_01", locale="en")

        self.assertEqual([10], hungry_faun.get("allowed_pet_type_ids"))
        self.assertEqual([26], counting_cerberus.get("allowed_pet_type_ids"))

    def test_episode_ids_are_unique_within_each_quest(self):
        for quest_id in ("hungry_faun_01", "counting_cerberus_01"):
            quest = load_quest_content(quest_id, locale="en")
            episode_ids = [episode.get("episode_id") for episode in quest.get("episodes", [])]
            self.assertEqual(
                len(episode_ids),
                len(set(episode_ids)),
                f"Duplicate episode_id in {quest_id}: {episode_ids}",
            )

    def test_locale_parity_for_quest_and_episode_ids(self):
        for quest_id in ("hungry_faun_01", "counting_cerberus_01"):
            quest_en = load_quest_content(quest_id, locale="en")
            quest_he = load_quest_content(quest_id, locale="he")

            self.assertEqual(quest_en.get("quest_id"), quest_he.get("quest_id"))
            self.assertEqual(quest_en.get("quest_line_id"), quest_he.get("quest_line_id"))
            self.assertEqual(
                quest_en.get("allowed_pet_type_ids"),
                quest_he.get("allowed_pet_type_ids"),
            )

            en_episode_ids = [ep.get("episode_id") for ep in quest_en.get("episodes", [])]
            he_episode_ids = [ep.get("episode_id") for ep in quest_he.get("episodes", [])]
            self.assertEqual(en_episode_ids, he_episode_ids)


if __name__ == "__main__":
    unittest.main()
