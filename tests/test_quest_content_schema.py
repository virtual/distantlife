import unittest
from pathlib import Path

from quest_content import (
    load_quest_content,
    validate_quest_file,
    resolve_gender_variant,
    replace_tokens,
    apply_personalization,
    load_and_personalize_quest,
)


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


class QuestRuntimeTestCase(unittest.TestCase):
    """Tests for quest runtime helpers: personalization, token replacement, gender resolution."""

    def test_resolve_gender_variant_male(self):
        text_obj = {"male": "He planted it.", "female": "She planted it.", "neutral": "They planted it."}
        resolved = resolve_gender_variant(text_obj, gender="male")
        self.assertEqual("He planted it.", resolved)

    def test_resolve_gender_variant_fallback_to_neutral(self):
        text_obj = {"male": "He did it.", "neutral": "It was done."}
        resolved = resolve_gender_variant(text_obj, gender="female")
        self.assertEqual("It was done.", resolved)

    def test_resolve_gender_variant_fallback_chain(self):
        text_obj = {"neutral": "Done."}
        resolved = resolve_gender_variant(text_obj, gender="male")
        self.assertEqual("Done.", resolved)

    def test_resolve_gender_variant_plain_string(self):
        text = "This is a plain string."
        resolved = resolve_gender_variant(text, gender="male")
        self.assertEqual("This is a plain string.", resolved)

    def test_replace_tokens_pet_name(self):
        text = "Hello {{pet_name}}, let's go!"
        result = replace_tokens(text, pet_name="Fluffy")
        self.assertEqual("Hello Fluffy, let's go!", result)

    def test_replace_tokens_multiple_occurrences(self):
        text = "{{pet_name}} met {{pet_name}} in the garden."
        result = replace_tokens(text, pet_name="Dragon")
        self.assertEqual("Dragon met Dragon in the garden.", result)

    def test_replace_tokens_html_escaping(self):
        text = "Pet: {{pet_name}}"
        result = replace_tokens(text, pet_name="<script>")
        self.assertEqual("Pet: &lt;script&gt;", result)

    def test_apply_personalization_gender_and_tokens(self):
        obj = {
            "story": {
                "male": "He went to {{pet_name}}'s house.",
                "female": "She went to {{pet_name}}'s house.",
                "neutral": "They went to {{pet_name}}'s house."
            }
        }
        result = apply_personalization(obj, gender="male", pet_name="Dragon")
        self.assertEqual("He went to Dragon's house.", result["story"])

    def test_apply_personalization_recursive_lists(self):
        obj = [
            {"text": {"neutral": "First: {{pet_name}}"}},
            {"text": {"neutral": "Second: {{pet_name}}"}}
        ]
        result = apply_personalization(obj, pet_name="Faun")
        self.assertEqual("First: Faun", result[0]["text"])
        self.assertEqual("Second: Faun", result[1]["text"])

    def test_load_and_personalize_quest_replaces_tokens(self):
        quest = load_and_personalize_quest("hungry_faun_01", locale="en", pet_name="MagicFaun")
        # Check that {{pet_name}} is replaced in story text
        first_episode_story = quest["episodes"][0]["story_text"]
        self.assertIn("MagicFaun", first_episode_story)
        # Verify token placeholder was replaced, not just concatenated
        self.assertNotIn("{{pet_name}}", first_episode_story)

    def test_load_and_personalize_quest_gender_resolution(self):
        quest = load_and_personalize_quest(
            "counting_cerberus_01", locale="en", gender="female", pet_name="Cerbie"
        )
        # Female speech bubble should be resolved
        first_bubble = quest["episodes"][0]["speech_bubble_lines"][0]
        # Gender-neutral first bubble doesn't differ, but let's check it's a string not a dict
        self.assertIsInstance(first_bubble, str)


if __name__ == "__main__":
    unittest.main()

