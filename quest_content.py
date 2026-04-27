import json
from pathlib import Path


REQUIRED_QUEST_KEYS = {
    "quest_id",
    "locale",
    "version",
    "review_status",
    "theme",
    "quest_type",
    "quest_line_id",
    "allowed_pet_type_ids",
    "title",
    "summary",
    "episodes",
}

REQUIRED_EPISODE_KEYS = {
    "episode_id",
    "title",
    "story_text",
    "quiz",
}

SUPPORTED_QUESTION_TYPES = {
    "cloze",
    "multiple_choice",
    "reorder",
    "count_sequence",
}


def get_quest_file_path(quest_id, locale="en", root_dir="quests"):
    return Path(root_dir) / locale / f"{quest_id}.json"


def load_quest_content(quest_id, locale="en", root_dir="quests"):
    quest_path = get_quest_file_path(quest_id, locale=locale, root_dir=root_dir)
    with quest_path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def _has_neutral_variant(value):
    return isinstance(value, dict) and "neutral" in value and isinstance(value["neutral"], str)


def _validate_question_shape(question, episode_id, question_index):
    errors = []
    location = f"episode '{episode_id}', question {question_index}"

    q_type = question.get("type")
    if q_type not in SUPPORTED_QUESTION_TYPES:
        errors.append(f"Unsupported question type in {location}: {q_type}")
        return errors

    if q_type == "cloze":
        if "prompt" not in question:
            errors.append(f"Missing cloze prompt in {location}")
        elif isinstance(question.get("prompt"), dict) and not _has_neutral_variant(question.get("prompt")):
            errors.append(f"Missing neutral prompt variant in {location}")

        if not isinstance(question.get("answer"), str) or not question.get("answer").strip():
            errors.append(f"Missing or invalid cloze answer in {location}")

    elif q_type == "multiple_choice":
        options = question.get("options")
        answer = question.get("answer")
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"multiple_choice options must be a list with at least 2 entries in {location}")
        if answer not in options:
            errors.append(f"multiple_choice answer must be one of the provided options in {location}")

    elif q_type == "reorder":
        items = question.get("items")
        correct_order = question.get("correct_order")

        if not isinstance(items, list) or len(items) < 2:
            errors.append(f"reorder items must be a list with at least 2 entries in {location}")

        if not isinstance(correct_order, list) or len(correct_order) != len(items or []):
            errors.append(f"reorder correct_order must be a list matching items length in {location}")
        else:
            expected = list(range(1, len(items) + 1))
            if sorted(correct_order) != expected:
                errors.append(f"reorder correct_order must contain 1..N exactly once in {location}")

    elif q_type == "count_sequence":
        options = question.get("options")
        answer = question.get("answer")

        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"count_sequence options must be a list with at least 2 entries in {location}")

        if not isinstance(answer, list) or len(answer) < 2:
            errors.append(f"count_sequence answer must be a list with at least 2 entries in {location}")

    return errors


def validate_quest_content(quest):
    errors = []

    missing_keys = REQUIRED_QUEST_KEYS - set(quest.keys())
    if missing_keys:
        errors.append(f"Missing required quest keys: {sorted(missing_keys)}")

    allowed_pet_type_ids = quest.get("allowed_pet_type_ids")
    if not isinstance(allowed_pet_type_ids, list):
        errors.append("allowed_pet_type_ids must be a list")

    episodes = quest.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        errors.append("episodes must be a non-empty list")
        return errors

    seen_episode_ids = set()

    for episode in episodes:
        if not isinstance(episode, dict):
            errors.append("Each episode must be an object")
            continue

        missing_episode_keys = REQUIRED_EPISODE_KEYS - set(episode.keys())
        if missing_episode_keys:
            errors.append(f"Episode missing required keys: {sorted(missing_episode_keys)}")

        episode_id = episode.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id.strip():
            errors.append("episode_id must be a non-empty string")
            episode_id = "<unknown_episode>"
        elif episode_id in seen_episode_ids:
            errors.append(f"Duplicate episode_id: {episode_id}")
        else:
            seen_episode_ids.add(episode_id)

        story_text = episode.get("story_text")
        if not _has_neutral_variant(story_text):
            errors.append(f"story_text must include neutral variant in episode '{episode_id}'")

        speech_bubble_lines = episode.get("speech_bubble_lines", [])
        if not isinstance(speech_bubble_lines, list):
            errors.append(f"speech_bubble_lines must be a list in episode '{episode_id}'")
        else:
            for i, line in enumerate(speech_bubble_lines, start=1):
                if not _has_neutral_variant(line):
                    errors.append(
                        f"speech_bubble_lines[{i}] must include neutral variant in episode '{episode_id}'"
                    )

        quiz = episode.get("quiz")
        if not isinstance(quiz, dict):
            errors.append(f"quiz must be an object in episode '{episode_id}'")
            continue

        questions = quiz.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append(f"quiz.questions must be a non-empty list in episode '{episode_id}'")
            continue

        for q_index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                errors.append(f"Question {q_index} must be an object in episode '{episode_id}'")
                continue
            errors.extend(_validate_question_shape(question, episode_id, q_index))

    return errors


def validate_quest_file(file_path):
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file_obj:
        quest = json.load(file_obj)
    return validate_quest_content(quest)
