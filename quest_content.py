import json
from pathlib import Path
import logging

# Logger for vocabulary resolution debugging
logger = logging.getLogger("distantlife.vocab")
if not logger.handlers:
    fh = logging.FileHandler("vocab_resolution.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)


REQUIRED_QUEST_KEYS = {
    "meta",
    "quest_id",
    "locales",
}

REQUIRED_EPISODE_KEYS = {
    "episode_id",
    "title",
    "story_sentences",
    "quiz",
}

SUPPORTED_QUESTION_TYPES = {
    "cloze",
    "multiple_choice",
    "reorder",
    "count_sequence",
}


def get_quest_file_path(quest_id, root_dir="quests"):
    """Locate the combined quest JSON for a given quest_id under root_dir.

    Searches for files matching "**/{quest_id}.json" and returns the first match.
    Raises FileNotFoundError if not found.
    """
    root = Path(root_dir)
    matches = [
        path
        for path in root.rglob(f"{quest_id}.json")
        if path.is_file() and path.parent.name == quest_id
    ]
    if not matches:
        raise FileNotFoundError(f"Quest file for '{quest_id}' not found under {root_dir}")
    return sorted(matches)[0]


def list_quest_ids(root_dir="quests"):
    """List all quest IDs by looking for combined quest files under root_dir.

    Returns stems of files matching `**/*.json` directly under per-quest paths.
    """
    root = Path(root_dir)
    if not root.exists():
        return []
    # Find only canonical quest files: <quest_folder>/<quest_id>.json
    files = [p for p in root.rglob("*.json") if p.is_file() and p.parent.name == p.stem]
    # Return unique stems
    ids = sorted({p.stem for p in files})
    return ids


def load_quest_content(quest_id, locale=None, root_dir="quests"):
    """
    Load combined quest content for a quest_id. The combined file contains all locales.

    Args:
        quest_id: identifier for the quest (matches filename without .json)
        locale: ignored at load time (kept for compatibility with callers)
        root_dir: quest directory root
    Returns:
        dict: combined quest content loaded from JSON
    Raises: FileNotFoundError if the quest file does not exist
    """
    quest_path = get_quest_file_path(quest_id, root_dir=root_dir)
    with quest_path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def get_locale_view(quest_obj, locale):
    """Return a localized view of a combined quest object.

    The returned view matches the previous per-locale quest shape expected by templates and routes:
    - meta, quest_id, unlock_cost, quest_line_id, allowed_pet_type_ids
    - title, summary, locale, theme
    - episodes: list of episode objects for that locale
    """
    locales = quest_obj.get("locales")
    if not isinstance(locales, dict):
        raise ValueError("Quest object missing 'locales' mapping")
    locale_data = locales.get(locale)
    if not locale_data:
        raise ValueError(f"Locale '{locale}' not found in quest '{quest_obj.get('quest_id')}'")
    view = {
        "meta": quest_obj.get("meta"),
        "quest_id": quest_obj.get("quest_id"),
        "unlock_cost": quest_obj.get("unlock_cost"),
        "quest_line_id": quest_obj.get("quest_line_id"),
        "allowed_pet_type_ids": quest_obj.get("allowed_pet_type_ids", []),
        "title": locale_data.get("title"),
        "summary": locale_data.get("summary"),
        "locale": locale_data.get("locale", locale),
        "theme": locale_data.get("theme"),
        "episodes": locale_data.get("episodes", []),
    }
    return view


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
    from normalization import has_nikkud
    
    db = get_db_connection()
    logger.info("get_vocabulary_with_translations called: targets=%s learning_lang_id=%s preferred_lang_id=%s", vocabulary_targets, learning_lang_id, preferred_lang_id)
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
            # Get primary (unvocalized) form
            primary_form = db.execute(
                """
                SELECT value
                FROM lemma_form
                WHERE lemma_id = ? AND language_id = ? AND is_primary = 1
                LIMIT 1
                """,
                (lemma_id, learning_lang_id),
            ).fetchone()

            # Look for a vocalized (nikkud) form in non-primary lemma_form rows
            vocalized_form = None
            vocal_rows = db.execute(
                """
                SELECT value
                FROM lemma_form
                WHERE lemma_id = ? AND language_id = ? AND (is_primary = 0 OR is_primary IS NULL)
                ORDER BY id ASC
                """,
                (lemma_id, learning_lang_id),
            ).fetchall()
            for vr in vocal_rows:
                if vr and vr['value'] and has_nikkud(vr['value']):
                    vocalized_form = vr['value']
                    break

            if vocalized_form:
                word_str = vocalized_form
            elif primary_form is not None:
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

        logger.info("Resolving target=%s -> lemma_id=%s word_str=%s", target, lemma_id, word_str)
        
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
        
        # TODO: also return the vocalized form in the learning language if available 
        vocabulary_with_translations.append({
            'word': word_str,
            'translation': translation or '?'
        })
        logger.info("Result for target=%s: lemma_id=%s word=%s translation=%s", target, lemma_id, word_str, translation or '?')
    
    return vocabulary_with_translations


def _resolve_vocabulary_target_ids(vocabulary_targets, learning_lang_id):
    """
    Resolve vocabulary target IDs from a list of targets that may include lemma IDs or surface forms.
    
    Args:
            vocabulary_targets: list of targets which can be integers (lemma IDs) or strings (surface forms)
            learning_lang_id: language ID of the learning language for resolving surface forms
    Returns:
        list of resolved lemma IDs corresponding to the vocabulary targets
    """
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
    """
    Get quest board entries for a user, determining availability based on their active pet and owned pets.
    Args:
        user_id: ID of the user for whom to get quest entries
        locale: language code for quest content
        root_dir: root directory where quest JSON files are stored
    Returns:
        list of dicts, each containing quest details and availability state
    """
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
    for quest_id in list_quest_ids(root_dir=root_dir):
        quest_obj = load_quest_content(quest_id, root_dir=root_dir)
        try:
            quest = get_locale_view(quest_obj, locale)
        except Exception:
            # Skip quests that don't have the requested locale
            continue
        allowed_pet_type_ids = quest.get("allowed_pet_type_ids", [])

        if not allowed_pet_type_ids:
            allowed_pet_label = "All pets"
        else:
            allowed_pet_label = ", ".join(
                allowed_pet_labels.get(int(pet_type_id), f"Pet type {pet_type_id}")
                for pet_type_id in allowed_pet_type_ids
            )

        # Determine if the quest is switchable based on owned pets and allowed pets
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

        # Add the quest entry with all relevant details and computed state
        entries.append(
            {
                "quest_id": quest["quest_id"],
                "title": quest["title"],
                "summary": quest["summary"],
                "quest_line_id": quest.get("quest_line_id"),
                "allowed_pet_type_ids": allowed_pet_type_ids,
                "allowed_pet_label": allowed_pet_label,
                "episode_count": len(quest.get("episodes", [])),
                "state": state,
                "switchable": switchable,
                "lock_reason_label": lock_reason_label,
            }
        )

    return [entry for entry in entries if entry.get("episode_count", 0) > 0]

def _has_neutral_variant(value):
    """
    Check if a value is a dict with a 'neutral' key that has a string value.
    Args:
        value: the value to check, which can be a string or a dict with gender
    Returns:
        bool: True if value is a dict with a 'neutral' key that is a string, False otherwise
    """
    return isinstance(value, dict) and "neutral" in value and isinstance(value["neutral"], str)

def _validate_question_shape(question, episode_id, question_index):
    """
    Validate the shape of a quiz question based on its type and required fields.
    Args:
        question: dict representing the quiz question
        episode_id: ID of the episode for error reporting
        question_index: index of the question within the episode for error reporting
    Returns:
        list of error messages (empty if no errors)
    """

    errors = []
    location = f"episode '{episode_id}', question {question_index}"

    # Validate that 'type' field is present and supported
    q_type = question.get("type")
    if q_type not in SUPPORTED_QUESTION_TYPES:
        errors.append(f"Unsupported question type in {location}: {q_type}")
        return errors

    # Validate required fields based on question type
    # For cloze questions, sentence_id and answer are required.
    if q_type == "cloze":
        sentence_id = question.get("sentence_id")
        if not isinstance(sentence_id, str) or not sentence_id.strip():
            errors.append(f"Missing or invalid cloze sentence_id in {location}")

        if not isinstance(question.get("answer"), str) or not question.get("answer").strip():
            errors.append(f"Missing or invalid cloze answer in {location}")

    # Additional validation for other question types can be added here as needed.
    elif q_type == "multiple_choice":
        options = question.get("options")
        answer = question.get("answer")
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"multiple_choice options must be a list with at least 2 entries in {location}")
        if answer not in options:
            errors.append(f"multiple_choice answer must be one of the provided options in {location}")

    # Additional question types like reorder and count_sequence 
    # can be validated here as needed.
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
    """
    Validate the structure and content of a quest dict against expected schema.
    Args:
        quest: dict representing the quest content
    Returns:
        list of error messages (empty if no errors)
    """
    errors = []

    # Top-level combined quest shape
    if not isinstance(quest, dict):
        return ["Quest must be a JSON object"]

    # Check meta
    meta = quest.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    else:
        if meta.get("generator") != "quest_pipeline_v1":
            errors.append("meta.generator must be 'quest_pipeline_v1'")
        generated_at = meta.get("generated_at")
        if not isinstance(generated_at, str) or not generated_at.strip():
            errors.append("meta.generated_at must be a non-empty string")

    if "quest_id" not in quest or not isinstance(quest.get("quest_id"), str):
        errors.append("quest_id must be a non-empty string")

    locales = quest.get("locales")
    if not isinstance(locales, dict) or not locales:
        errors.append("locales must be a non-empty mapping of locale codes to locale data")
        return errors

    # Validate each locale's episodes using episode-level validation
    for locale_code, locale_data in locales.items():
        if not isinstance(locale_data, dict):
            errors.append(f"locale '{locale_code}' must be an object")
            continue

        episodes = locale_data.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            errors.append(f"locale '{locale_code}' must include a non-empty episodes list")
            continue

        seen_episode_ids = set()
        for episode in episodes:
            if not isinstance(episode, dict):
                errors.append(f"Each episode in locale '{locale_code}' must be an object")
                continue

            missing_episode_keys = REQUIRED_EPISODE_KEYS - set(episode.keys())
            if missing_episode_keys:
                errors.append(f"Episode missing required keys in locale '{locale_code}': {sorted(missing_episode_keys)}")

            episode_id = episode.get("episode_id")
            if not isinstance(episode_id, str) or not episode_id.strip():
                errors.append(f"episode_id must be a non-empty string in locale '{locale_code}'")
                episode_id = "<unknown_episode>"
            elif episode_id in seen_episode_ids:
                errors.append(f"Duplicate episode_id: {episode_id} in locale '{locale_code}'")
            else:
                seen_episode_ids.add(episode_id)

            # story_sentences validation
            story_sentences = episode.get("story_sentences")
            if not isinstance(story_sentences, list) or not story_sentences:
                errors.append(f"story_sentences must be a non-empty list in episode '{episode_id}' (locale '{locale_code}')")
                continue

            story_sentence_ids = set()
            for i, sentence in enumerate(story_sentences, start=1):
                if not _has_neutral_variant(sentence):
                    errors.append(f"story_sentences[{i}] must include neutral variant in episode '{episode_id}' (locale '{locale_code}')")
                    continue

                sentence_id = sentence.get("id") if isinstance(sentence, dict) else None
                if not isinstance(sentence_id, str) or not sentence_id.strip():
                    errors.append(f"story_sentences[{i}] must include a non-empty id in episode '{episode_id}' (locale '{locale_code}')")
                    continue

                if sentence_id in story_sentence_ids:
                    errors.append(f"Duplicate sentence id '{sentence_id}' in episode '{episode_id}' (locale '{locale_code}')")
                else:
                    story_sentence_ids.add(sentence_id)

            # quiz validation
            quiz = episode.get("quiz")
            if not isinstance(quiz, dict):
                errors.append(f"quiz must be an object in episode '{episode_id}' (locale '{locale_code}')")
                continue

            questions = quiz.get("questions")
            if not isinstance(questions, list):
                errors.append(f"quiz.questions must be a list in episode '{episode_id}' (locale '{locale_code}')")
                continue
            # Empty questions list is allowed (no quiz for this locale/episode)
            if not questions:
                continue

            for q_index, question in enumerate(questions, start=1):
                if not isinstance(question, dict):
                    errors.append(f"Question {q_index} must be an object in episode '{episode_id}' (locale '{locale_code}')")
                    continue
                errors.extend(_validate_question_shape(question, episode_id, q_index))

                if question.get("type") == "cloze":
                    sentence_id = question.get("sentence_id")
                    if isinstance(sentence_id, str) and sentence_id.strip():
                        if sentence_id not in story_sentence_ids:
                            errors.append(f"cloze sentence_id not found in episode '{episode_id}', question {q_index}: {sentence_id} (locale '{locale_code}')")

    return errors


def validate_quest_file(file_path):
    """
    Validate a quest JSON file against the expected schema.
    Args:
        file_path: path to the quest JSON file
    Returns:
        list of error messages (empty if no errors)
    """
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
    quest_obj = load_quest_content(quest_id, locale=locale, root_dir=root_dir)
    quest = get_locale_view(quest_obj, locale)

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
    quest_obj = load_quest_content(quest_id, locale=locale, root_dir=root_dir)
    quest = get_locale_view(quest_obj, locale)

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

    # Preserve sentence IDs alongside resolved sentence text for stable quiz lookup.
    story_sentence_refs = []
    for sentence in episode.get("story_sentences", []):
        if not isinstance(sentence, dict):
            continue

        sentence_id = sentence.get("id")
        if not isinstance(sentence_id, str) or not sentence_id.strip():
            continue

        resolved_text = replace_tokens(resolve_gender_variant(sentence, gender), **context)
        story_sentence_refs.append({"id": sentence_id, "text": resolved_text})

    personalized_episode["story_sentence_refs"] = story_sentence_refs
    personalized_episode["story_sentences"] = [ref["text"] for ref in story_sentence_refs]

    learning_lang_id = None
    from connections import get_db_connection

    db = get_db_connection()
    locale_row = db.execute("SELECT id FROM languages WHERE charcode = ? LIMIT 1", (locale,)).fetchone()
    if locale_row is not None:
        learning_lang_id = int(locale_row["id"])

    vocabulary_target_ids = episode.get("vocabulary_target_ids")
    if learning_lang_id is not None:
        if vocabulary_target_ids is not None:
            # If explicit lemma IDs are provided, use them directly
            resolved_target_ids = [int(t) for t in vocabulary_target_ids]
        else:
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
        "title": quest.get("title"),
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
    
    quest_obj = load_quest_content(quest_id, locale=locale)
    try:
        quest = get_locale_view(quest_obj, locale)
    except Exception:
        quest = {}
    allowed_pet_type_ids = quest.get("allowed_pet_type_ids", [])
    
    # Empty list means all pets allowed
    if not allowed_pet_type_ids:
        return (True, None)
    
    # Check if user's pet type is in allowed list
    if pet.get("type_id") in allowed_pet_type_ids:
        return (True, None)
    else:
        return (False, "pet_type_not_allowed")
