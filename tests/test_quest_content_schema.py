import unittest
from pathlib import Path

from quest_content import (
    load_quest_content,
    validate_quest_file,
    validate_quest_content,
    resolve_gender_variant,
    replace_tokens,
    apply_personalization,
    load_and_personalize_quest,
    load_episode_from_quest,
)
from quest_content import get_locale_view


class QuestContentSchemaTestCase(unittest.TestCase):
    """Validation tests for JSON-based quest content."""

    def test_hungry_faun_file_validates(self):
        errors = validate_quest_file(Path("quests/garden_adventure/garden_adventure.json"))
        self.assertEqual([], errors, f"garden_adventure has schema errors: {errors}")

    def test_counting_cerberus_file_validates(self):
        # legacy counting_cerberus removed; use garden_adventure as canonical fixture
        errors = validate_quest_file(Path("quests/garden_adventure/garden_adventure.json"))
        self.assertEqual([], errors, f"garden_adventure has schema errors: {errors}")

    def test_hungry_faun_hebrew_file_validates(self):
        errors = validate_quest_file(Path("quests/garden_adventure/garden_adventure.json"))
        self.assertEqual([], errors, f"garden_adventure (he) has schema errors: {errors}")

    def test_counting_cerberus_hebrew_file_validates(self):
        # counting_cerberus removed; reuse garden_adventure fixture
        errors = validate_quest_file(Path("quests/garden_adventure/garden_adventure.json"))
        self.assertEqual([], errors, f"garden_adventure (he) has schema errors: {errors}")

    def test_pet_restrictions_are_present(self):
        hungry_obj = load_quest_content("garden_adventure", locale="en")
        self.assertEqual([10], hungry_obj.get("allowed_pet_type_ids"))

    def test_episode_ids_are_unique_within_each_quest(self):
        for quest_id in ("garden_adventure",):
            quest_obj = load_quest_content(quest_id, locale="en")
            quest = get_locale_view(quest_obj, "en")
            episode_ids = [episode.get("episode_id") for episode in quest.get("episodes", [])]
            self.assertEqual(
                len(episode_ids),
                len(set(episode_ids)),
                f"Duplicate episode_id in {quest_id}: {episode_ids}",
            )

    def test_locale_parity_for_quest_and_episode_ids(self):
        for quest_id in ("garden_adventure",):
            quest_obj_en = load_quest_content(quest_id, locale="en")
            quest_obj_he = load_quest_content(quest_id, locale="he")
            quest_en = get_locale_view(quest_obj_en, "en")
            quest_he = get_locale_view(quest_obj_he, "he")

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
        quest = load_and_personalize_quest("garden_adventure", locale="en", pet_name="MagicFaun")
        # Check that {{pet_name}} is replaced in personalized story sentences
        first_episode_story = quest["episodes"][0]["story_sentences"][0]
        self.assertIn("MagicFaun", first_episode_story)
        # Verify token placeholder was replaced, not just concatenated
        self.assertNotIn("{{pet_name}}", first_episode_story)

    def test_load_and_personalize_quest_gender_resolution(self):
        quest = load_and_personalize_quest(
            "garden_adventure", locale="en", gender="female", pet_name="Cerbie"
        )
        first_sentence = quest["episodes"][0]["story_sentences"][0]
        self.assertIsInstance(first_sentence, str)

    def test_load_episode_exposes_resolved_vocabulary_target_ids(self):
        _, episode = load_episode_from_quest(
            "garden_adventure",
            "garden_adventure_ep1",
            locale="en",
            pet_name="Cerbie",
        )
        self.assertIn("resolved_vocabulary_target_ids", episode)
        self.assertIsInstance(episode["resolved_vocabulary_target_ids"], list)
        self.assertGreater(len(episode["resolved_vocabulary_target_ids"]), 0)


class QuestVocabularyReferenceSchemaTestCase(unittest.TestCase):
    def _minimal_valid_quest(self):
        # Return a minimal quest in the combined per-quest format with locales mapping
        return {
            "meta": {
                "schema_version": "2.0.0",
                "generator": "quest_pipeline_v1",
                "generated_at": "2026-05-19T00:00:00",
            },
            "quest_id": "demo_quest",
            "quest_line_id": "demo_line",
            "unlock_cost": 0,
            "allowed_pet_type_ids": [10],
            "locales": {
                "en": {
                    "locale": "en",
                    "theme": "demo",
                    "title": "Demo",
                    "summary": "Demo summary",
                    "episodes": [
                        {
                            "episode_id": "demo_ep_1",
                            "title": "Episode 1",
                            "story_sentences": [
                                {
                                    "id": "s1",
                                    "male": "Story.",
                                    "female": "Story.",
                                    "neutral": "Story.",
                                }
                            ],
                            "quiz": {"questions": [{"type": "multiple_choice", "prompt": "Choose", "options": ["a", "b"], "answer": "a"}]},
                        }
                    ],
                }
            },
        }

    def test_vocab_target_ids_accepts_integer_ids(self):
        quest = self._minimal_valid_quest()
        quest["episodes"][0]["vocabulary_target_ids"] = [101, 202, 303]
        errors = validate_quest_content(quest)
        self.assertEqual([], errors)

    def test_vocab_target_ids_rejects_non_integer_values(self):
        quest = self._minimal_valid_quest()
        quest["episodes"][0]["vocabulary_target_ids"] = [101, "bad-id", 303]
        errors = validate_quest_content(quest)
        self.assertTrue(
            any("vocabulary_target_ids" in err for err in errors),
            f"Expected vocabulary_target_ids validation error, got: {errors}",
        )

    def test_cloze_requires_sentence_id(self):
        quest = self._minimal_valid_quest()
        quest["episodes"][0]["quiz"]["questions"] = [
            {
                "type": "cloze",
                "answer": "Story",
            }
        ]
        errors = validate_quest_content(quest)
        self.assertTrue(
            any("sentence_id" in err for err in errors),
            f"Expected sentence_id validation error, got: {errors}",
        )

    def test_story_sentence_requires_id(self):
        quest = self._minimal_valid_quest()
        del quest["episodes"][0]["story_sentences"][0]["id"]
        errors = validate_quest_content(quest)
        self.assertTrue(
            any("story_sentences" in err and "id" in err for err in errors),
            f"Expected story sentence id validation error, got: {errors}",
        )

    def test_cloze_sentence_id_must_exist(self):
        quest = self._minimal_valid_quest()
        quest["episodes"][0]["quiz"]["questions"] = [
            {
                "type": "cloze",
                "answer": "Story",
                "sentence_id": "missing",
            }
        ]
        errors = validate_quest_content(quest)
        self.assertTrue(
            any("sentence_id not found" in err for err in errors),
            f"Expected sentence_id not found validation error, got: {errors}",
        )


if __name__ == "__main__":
    unittest.main()

