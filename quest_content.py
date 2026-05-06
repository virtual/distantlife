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


def list_quest_ids(locale="en", root_dir="quests"):
    """
    List all available quest IDs for a given locale.
    
    Args:
        locale: language code (en, he, etc.)
        root_dir: quest directory root
    
    Returns:
        list: quest IDs (filenames without .json extension)
    """
    quest_dir = Path(root_dir) / locale
    if not quest_dir.exists():
        return []
    
    return sorted([f.stem for f in quest_dir.glob("*.json")])


def load_quest_content(quest_id, locale="en", root_dir="quests"):
    quest_path = get_quest_file_path(quest_id, locale=locale, root_dir=root_dir)
    with quest_path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def get_vocabulary_with_translations(vocabulary_targets, learning_lang_id, preferred_lang_id):
    """
    Get vocabulary targets with translations using the lemma-based schema.
    
    Args:
        vocabulary_targets: list of words in the learning language
        learning_lang_id: language ID of the learning language
        preferred_lang_id: language ID of the preferred language
    
    Returns:
        list of dicts with 'word' (learning lang) and 'translation' (preferred lang)
    """
    from connections import get_db_connection
    
    db = get_db_connection()
    vocabulary_with_translations = []
    
    for target in vocabulary_targets:
        lemma_id = None
        word_str = None

        # New canonical contract: vocabulary target is a lemma ID.
        if isinstance(target, int):
            lemma_id = target
        elif isinstance(target, str) and target.strip().isdigit():
            lemma_id = int(target.strip())
        else:
            word_str = str(target)

        if lemma_id is not None:
            primary_form = db.execute(
                """
                SELECT value
                FROM lemma_form
                WHERE lemma_id = ? AND language_id = ? AND is_primary = 1
                LIMIT 1
                """,
                (lemma_id, learning_lang_id),
            ).fetchone()
            if primary_form is not None:
                word_str = primary_form['value']
            else:
                # Keep deterministic fallback text in UI for bad references.
                word_str = f"#{lemma_id}"
        else:
            # Legacy contract: vocabulary target is surface text.
            result = db.execute("""
                SELECT lf.lemma_id
                FROM lemma_form lf
                WHERE lf.language_id = ? AND LOWER(lf.value) = LOWER(?)
                LIMIT 1
            """, (learning_lang_id, word_str)).fetchone()
            if result is not None:
                lemma_id = int(result['lemma_id'])
        
        translation = None
        if lemma_id is not None:
            # Get the primary sense for this lemma.
            sense_result = db.execute("""
                SELECT s.id
                FROM sense s
                WHERE s.lemma_id = ? AND s.is_primary = 1
                LIMIT 1
            """, (int(lemma_id),)).fetchone()
            
            if sense_result:
                source_sense_id = sense_result['id']
                
                # Find the translated sense via sense_translation
                trans_sense_result = db.execute("""
                    SELECT st.target_sense_id
                    FROM sense_translation st
                    WHERE st.source_sense_id = ?
                    LIMIT 1
                """, (source_sense_id,)).fetchone()
                
                if trans_sense_result:
                    target_sense_id = trans_sense_result['target_sense_id']
                    
                    # Get the lemma for the target sense and find its form in preferred language
                    trans_form_result = db.execute("""
                        SELECT lf.value
                        FROM lemma_form lf
                        JOIN sense s ON s.lemma_id = lf.lemma_id
                        WHERE s.id = ? AND lf.language_id = ? AND lf.is_primary = 1
                        LIMIT 1
                    """, (target_sense_id, preferred_lang_id)).fetchone()
                    
                    if trans_form_result:
                        translation = trans_form_result['value']
        
        vocabulary_with_translations.append({
            'word': word_str,
            'translation': translation or '?'
        })
    
    return vocabulary_with_translations


def _resolve_vocabulary_target_ids(vocabulary_targets, learning_lang_id):
    from connections import get_db_connection

    db = get_db_connection()
    resolved_ids = []

    for target in vocabulary_targets or []:
        if isinstance(target, int):
            resolved_ids.append(int(target))
            continue

        if isinstance(target, str) and target.strip().isdigit():
            resolved_ids.append(int(target.strip()))
            continue

        if not isinstance(target, str):
            target = str(target)

        result = db.execute(
            """
            SELECT lf.lemma_id
            FROM lemma_form lf
            WHERE lf.language_id = ? AND LOWER(lf.value) = LOWER(?)
            LIMIT 1
            """,
            (learning_lang_id, target),
        ).fetchone()
        if result is not None:
            resolved_ids.append(int(result["lemma_id"]))

    return resolved_ids





def get_quest_board_entries(user_id, locale="en", root_dir="quests"):
    from helpers import get_active_pet_for_user, get_owned_pet_type_ids_for_user

    active_pet = get_active_pet_for_user(user_id)
    active_pet_type_id = active_pet["type_id"] if active_pet else None
    owned_pet_type_ids = set(get_owned_pet_type_ids_for_user(user_id))

    allowed_pet_labels = {
        1: "Dragon",
        6: "Genie",
        10: "Faun",
        16: "Cyclops",
        26: "Cerberus",
    }

    entries = []
    for quest_id in list_quest_ids(locale=locale, root_dir=root_dir):
        quest = load_quest_content(quest_id, locale=locale, root_dir=root_dir)
        allowed_pet_type_ids = quest.get("allowed_pet_type_ids", [])

        if not allowed_pet_type_ids:
            allowed_pet_label = "All pets"
        else:
            allowed_pet_label = ", ".join(
                allowed_pet_labels.get(int(pet_type_id), f"Pet type {pet_type_id}")
                for pet_type_id in allowed_pet_type_ids
            )

        switchable = bool(
            allowed_pet_type_ids
            and owned_pet_type_ids.intersection(set(int(pet_type_id) for pet_type_id in allowed_pet_type_ids))
        )

        if active_pet_type_id is None:
            state = "locked"
            lock_reason_label = "Adopt a pet to start quests" if not switchable else f"Available if you switch to {allowed_pet_label}"
        elif not allowed_pet_type_ids or active_pet_type_id in allowed_pet_type_ids:
            state = "available"
            switchable = False
            lock_reason_label = ""
        else:
            state = "locked"
            if switchable:
                lock_reason_label = f"Available if you switch to {allowed_pet_label}"
            else:
                lock_reason_label = f"Requires {allowed_pet_label}"

        entries.append(
            {
                "quest_id": quest["quest_id"],
                "title": quest["title"],
                "summary": quest["summary"],
                "quest_line_id": quest["quest_line_id"],
                "allowed_pet_type_ids": allowed_pet_type_ids,
                "allowed_pet_label": allowed_pet_label,
                "episode_count": len(quest.get("episodes", [])),
                "state": state,
                "switchable": switchable,
                "lock_reason_label": lock_reason_label,
            }
        )

    return entries


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

        vocabulary_targets = episode.get("vocabulary_targets")
        vocabulary_target_ids = episode.get("vocabulary_target_ids")
        if vocabulary_targets is not None and not isinstance(vocabulary_targets, list):
            errors.append(f"vocabulary_targets must be a list in episode '{episode_id}'")
        if vocabulary_target_ids is not None:
            if not isinstance(vocabulary_target_ids, list):
                errors.append(f"vocabulary_target_ids must be a list in episode '{episode_id}'")
            else:
                for i, target_id in enumerate(vocabulary_target_ids, start=1):
                    if not isinstance(target_id, int) and not (
                        isinstance(target_id, str) and target_id.strip().isdigit()
                    ):
                        errors.append(
                            f"vocabulary_target_ids[{i}] must be an integer ID in episode '{episode_id}'"
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


def load_episode_from_quest(quest_id, episode_id, locale="en", gender="neutral", pet_name=None, root_dir="quests"):
    """
    Load a specific episode from a quest and apply personalization.
    
    Args:
        quest_id: quest identifier
        episode_id: episode identifier within the quest
        locale: language code (en, he, etc.)
        gender: preferred gender for story text
        pet_name: pet name for token replacement
        root_dir: quest directory root
    
    Returns:
        tuple: (quest_metadata, episode) where quest_metadata contains quest-level info
               and episode is the personalized episode dict with episode index
    
    Raises:
        FileNotFoundError: if quest file not found
        ValueError: if episode not found or quest content is invalid
    """
    quest = load_quest_content(quest_id, locale=locale, root_dir=root_dir)
    
    episodes = quest.get("episodes", [])
    episode_index = None
    episode = None
    
    for idx, ep in enumerate(episodes):
        if ep.get("episode_id") == episode_id:
            episode_index = idx
            episode = ep
            break
    
    if episode is None:
        raise ValueError(f"Episode '{episode_id}' not found in quest '{quest_id}'")
    
    context = {}
    if pet_name:
        context["pet_name"] = pet_name
    
    personalized_episode = apply_personalization(episode, gender, **context)

    learning_lang_id = None
    from connections import get_db_connection

    db = get_db_connection()
    locale_row = db.execute("SELECT id FROM languages WHERE charcode = ? LIMIT 1", (locale,)).fetchone()
    if locale_row is not None:
        learning_lang_id = int(locale_row["id"])

    vocabulary_target_ids = episode.get("vocabulary_target_ids")
    if learning_lang_id is not None:
        resolved_target_ids = _resolve_vocabulary_target_ids(episode.get("vocabulary_targets"), learning_lang_id)
    else:
        resolved_target_ids = []

    if vocabulary_target_ids is not None:
        personalized_episode["vocabulary_target_ids"] = [int(target_id) for target_id in vocabulary_target_ids]

    personalized_episode["resolved_vocabulary_target_ids"] = resolved_target_ids
    
    # Add navigation info
    quest_metadata = {
        "quest_id": quest["quest_id"],
        "quest_line_id": quest.get("quest_line_id"),
        "title": quest["title"],
        "allowed_pet_label": quest.get("allowed_pet_label", ""),
        "locale": quest.get("locale", locale),
        "total_episodes": len(episodes),
        "episode_number": episode_index + 1,  # 1-based index for display
        "episode_index": episode_index,  # 0-based index for navigation
    }
    
    # Add episode navigation
    personalized_episode["episode_number"] = episode_index + 1
    personalized_episode["total_episodes"] = len(episodes)
    personalized_episode["has_previous"] = episode_index > 0
    personalized_episode["has_next"] = episode_index < len(episodes) - 1
    
    if episode_index > 0:
        personalized_episode["previous_episode_id"] = episodes[episode_index - 1].get("episode_id")
    if episode_index < len(episodes) - 1:
        personalized_episode["next_episode_id"] = episodes[episode_index + 1].get("episode_id")
    
    return (quest_metadata, personalized_episode)


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
