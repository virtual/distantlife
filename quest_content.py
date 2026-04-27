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


# ============================================================================
# Runtime Helpers: Token Replacement, Gender Resolution, and Access Control
# ============================================================================


def resolve_gender_variant(text_obj, gender="neutral"):
    """
    Resolve a gendered text object to a single string using fallback order.
    
    Args:
        text_obj: dict with keys like {"male": "...", "female": "...", "neutral": "..."}
                 or a plain string
        gender: preferred gender ("male", "female", or "neutral")
    
    Returns:
        str: resolved text, or empty string if no variant found
    
    Fallback order: requested gender -> neutral -> male -> female
    """
    if isinstance(text_obj, str):
        return text_obj
    
    if not isinstance(text_obj, dict):
        return ""
    
    # Try requested gender first
    if gender in text_obj and isinstance(text_obj[gender], str):
        return text_obj[gender]
    
    # Try neutral
    if "neutral" in text_obj and isinstance(text_obj["neutral"], str):
        return text_obj["neutral"]
    
    # Try male
    if "male" in text_obj and isinstance(text_obj["male"], str):
        return text_obj["male"]
    
    # Try female
    if "female" in text_obj and isinstance(text_obj["female"], str):
        return text_obj["female"]
    
    return ""


def replace_tokens(text, **context):
    """
    Replace template tokens in text using context values.
    
    Args:
        text: string with tokens like {{pet_name}}
        **context: keyword arguments, e.g., pet_name="Fluffy"
    
    Returns:
        str: text with tokens replaced, escaped for HTML safety
    
    Supported tokens:
        {{pet_name}}: pet name from context
    """
    if not text or not isinstance(text, str):
        return text
    
    # Simple replacement; values are escaped before insertion
    result = text
    for key, value in context.items():
        if value is not None:
            # Escape HTML special characters in user-provided values
            escaped_value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            result = result.replace(f"{{{{{key}}}}}", escaped_value)
    
    return result


def apply_personalization(obj, gender="neutral", **context):
    """
    Recursively apply gender resolution and token replacement to a quest object.
    
    Processes string values and dicts with gender variants.
    
    Args:
        obj: string, dict, list, or other value
        gender: preferred gender for variant resolution
        **context: template context for token replacement
    
    Returns:
        Personalized version of obj
    """
    if isinstance(obj, dict):
        # Check if this dict is a gender variant object (has gender keys)
        if any(k in obj for k in ("male", "female", "neutral")) and all(
            isinstance(v, str) or v is None for v in obj.values()
        ):
            resolved = resolve_gender_variant(obj, gender)
            return replace_tokens(resolved, **context)
        
        # Otherwise, recurse into dict values
        return {k: apply_personalization(v, gender, **context) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        return [apply_personalization(item, gender, **context) for item in obj]
    
    elif isinstance(obj, str):
        return replace_tokens(obj, **context)
    
    else:
        return obj


def load_and_personalize_quest(quest_id, locale="en", gender="neutral", pet_name=None, root_dir="quests"):
    """
    Load a quest and apply gender resolution and token replacement.
    
    Args:
        quest_id: quest identifier
        locale: language code (en, he, etc.)
        gender: preferred gender for story text
        pet_name: pet name for token replacement
        root_dir: quest directory root
    
    Returns:
        dict: personalized quest content
    
    Raises:
        FileNotFoundError: if quest file not found
        ValueError: if quest content is invalid
    """
    quest = load_quest_content(quest_id, locale=locale, root_dir=root_dir)
    
    context = {}
    if pet_name:
        context["pet_name"] = pet_name
    
    return apply_personalization(quest, gender, **context)


def can_user_access_quest(user_id, quest_id, locale="en"):
    """
    Check if a user can access a quest based on their active pet type.
    
    Args:
        user_id: user ID (requires active pet in session or DB)
        quest_id: quest identifier
        locale: language code for loading quest
    
    Returns:
        (bool, str): (can_access, reason) where reason is None if accessible,
                     else one of: "no_active_pet", "pet_type_not_allowed", "admin_bypass"
    
    Admin users always bypass restrictions.
    """
    # Import here to avoid circular dependency
    from helpers import is_admin, get_active_pet_for_user
    
    if is_admin():
        return (True, "admin_bypass")
    
    pet = get_active_pet_for_user(user_id)
    if not pet:
        return (False, "no_active_pet")
    
    quest = load_quest_content(quest_id, locale=locale)
    allowed_pet_type_ids = quest.get("allowed_pet_type_ids", [])
    
    # Empty list means all pets allowed
    if not allowed_pet_type_ids:
        return (True, None)
    
    # Check if user's pet type is in allowed list
    if pet.get("type_id") in allowed_pet_type_ids:
        return (True, None)
    else:
        return (False, "pet_type_not_allowed")
