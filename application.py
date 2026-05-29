import os
import random
import re
import sqlite3
import secrets
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import Flask, flash, redirect, render_template, request, session, has_request_context
from flask_session import Session
from tempfile import mkdtemp
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from flask_babel import Babel
from connections import REDIS_URL, get_db_connection, get_redis_client, close_db_connection
from quest_content import get_quest_board_entries, load_and_personalize_quest, can_user_access_quest, load_episode_from_quest, get_vocabulary_with_translations
from helpers import apology, login_required, adopted_pet_required, admin_required, usd, set_active_pet_in_session, set_languages, get_sets, get_set_by_id, get_words_by_set_id, get_role, get_word_translation, update_experience, session_get_int, resolve_canonical_sense_id, record_set_learned, record_words_learned, get_learning_progress, initialize_user_pet_unlocks, can_user_adopt_pet_type, get_adoptable_pet_types_for_user, get_active_pet_for_user, table_columns, choose_pet_gender, get_pet_gender_label, get_pet_gender_icon_class, get_learning_language_charcode, is_admin, has_completed_episode, record_episode_completed, get_level_from_exp, PASSWORD_RULES
import helpers
from fileparser import save_words
from normalization import compute_search_key, has_nikkud

r = get_redis_client()

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

LANGUAGES = {
    'en': 'English',
    'he': 'Hebrew'
}
app.config['LANGUAGES'] = LANGUAGES

def get_locale():
    """Set localization for text keys"""
    if has_request_context() and session.get("language") is not None:
        return session.get('language')['charcode']
    return request.accept_languages.best_match(LANGUAGES.keys()) if has_request_context() else 'en'


babel = Babel(app, locale_selector=get_locale)


def resolve_language_direction(source=None):
    """Resolve a text direction for templates from session language data or a supplied value."""
    if isinstance(source, dict):
        source = source.get("dir") or source.get("learning_dir") or source.get("learning_charcode") or source.get("charcode")

    if source is None:
        lang = session.get("language") or {}
        source = lang.get("learning_dir") or lang.get("learning_charcode") or lang.get("charcode")

    if not source:
        return "ltr"

    value = str(source).lower()
    if value in ("rtl", "ltr"):
        return value
    return "rtl" if value == "he" else "ltr"


@app.template_filter('to_direction')
def to_direction(charcode):
    """
    Jinja2 filter to convert language charcode to text direction.
    
    Args:
        charcode: Language character code (e.g., 'he', 'en')
    
    Returns:
        'rtl' for right-to-left languages (Hebrew), 'ltr' for others
    """
    return resolve_language_direction(charcode)


@app.template_filter('get_level')
def get_level(total_exp):
    """
    Jinja2 filter to calculate level from total experience.
    Uses logarithmic (quadratic) scaling for experience requirements.
    """
    from helpers import get_level_from_exp
    return get_level_from_exp(int(total_exp))


@app.template_filter('get_level_progress')
def get_level_progress(total_exp):
    """
    Jinja2 filter to get level progress data from total experience.
    Returns a dict with level, current_exp, exp_for_next, and progress_percent.
    """
    from helpers import get_level_progress as calc_progress
    return calc_progress(int(total_exp))


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.before_request
def ensure_language_session():
    """
    Ensure `session['language']` contains learning language metadata (including `learning_dir`).
    This helps existing sessions created before recent schema/template changes to render direction correctly.
    """
    # Only attempt to set languages for authenticated users
    try:
        if session_get_int('user_id') is not None:
            lang = session.get('language') or {}
            if not lang.get('learning_dir') or not lang.get('learning_charcode'):
                set_languages(session_get_int('user_id'))
    except Exception:
        # Do not raise during request handling; best-effort refresh only
        pass


UPLOAD_FOLDER = 'static/files'
ALLOWED_UPLOAD_EXTENSIONS = {'.csv'}
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,30}$")
PET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 _'\-]{1,50}$")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.jinja_env.filters["usd"] = usd
app.config["SESSION_FILE_DIR"] = mkdtemp()

# Use an environment-provided secret in non-dev environments.
configured_secret = os.environ.get("SECRET_KEY")
flask_env = os.environ.get("FLASK_ENV", "development").lower()
is_dev_mode = flask_env == "development" or app.debug
if not configured_secret and flask_env == "production":
    raise RuntimeError("SECRET_KEY must be set in non-development environments")
app.secret_key = configured_secret or "dev-only-insecure-secret-key"

# Configure Redis for storing the session data on the server-side
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = r

csrf = CSRFProtect(app)


@app.context_processor
def inject_csrf_token():
    # Keep csrf_token available in templates even if extension init order changes.
    return {"csrf_token": generate_csrf}


@app.context_processor
def inject_admin_flag():
    return {"is_admin_user": is_admin() if session_get_int("user_id") is not None else False}


@app.context_processor
def inject_language_dir():
    return {"language_dir": resolve_language_direction}


@app.context_processor
def inject_password_rules():
    return {"password_rules": PASSWORD_RULES}

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=REDIS_URL,
)

Session(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

con = get_db_connection()
db = con


def validate_username(username):
    if not username:
        return "must provide username"
    if not USERNAME_PATTERN.fullmatch(username):
        return "username must be 3-30 chars and only letters, numbers, dot, underscore, or hyphen"
    return None


def validate_password_strength(password):
    if not password:
        return "must provide password"

    rules = PASSWORD_RULES
    if len(password) < int(rules.get("min_length", 12)):
        return f"password must be at least {int(rules.get('min_length', 12))} characters"
    if rules.get("require_uppercase") and not re.search(r"[A-Z]", password):
        return "password must include an uppercase letter"
    if rules.get("require_lowercase") and not re.search(r"[a-z]", password):
        return "password must include a lowercase letter"
    if rules.get("require_number") and not re.search(r"\d", password):
        return "password must include a number"
    if rules.get("require_symbol") and not re.search(r"[^A-Za-z0-9]", password):
        return "password must include a symbol"
    return None


def parse_and_validate_language_id(language_id):
    try:
        parsed = int(language_id)
    except (TypeError, ValueError):
        return None

    exists = db.execute("SELECT 1 FROM languages WHERE id = ?", (parsed,)).fetchone()
    if not exists:
        return None
    return parsed


def format_timestamp(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        timestamp = value
    else:
        try:
            timestamp = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)

    return timestamp.strftime("%b %d, %Y")


def get_user_profile(identifier):
    query_by_id = (
        "SELECT username, id, full_name, email, preferred_lang, learning_lang, created_at, active_pet_id "
        "FROM users WHERE id = ?"
    )
    query_by_username = (
        "SELECT username, id, full_name, email, preferred_lang, learning_lang, created_at, active_pet_id "
        "FROM users WHERE username = ?"
    )
    identifier_text = str(identifier)

    if identifier_text.isdigit():
        user_row = db.execute(query_by_id, (int(identifier_text),)).fetchone()
        if user_row is None:
            user_row = db.execute(query_by_username, (identifier_text,)).fetchone()
        return user_row

    user_row = db.execute(query_by_username, (identifier_text,)).fetchone()
    if user_row is not None:
        return user_row

    try:
        user_id = int(identifier_text)
    except (TypeError, ValueError):
        return None

    return db.execute(query_by_id, (user_id,)).fetchone()


@app.teardown_appcontext
def close_db_connection_on_teardown(exception=None):
    close_db_connection()


def get_user_pets(user_id):
    return db.execute(
        """
        SELECT pets.id,
               pet_types.imgsrc,
               pet_types.pet_type,
               pets.created,
               pets.exp,
               pets.name,
               users.active_pet_id
        FROM owners
        JOIN pets ON pets.id = owners.pet_id
        JOIN pet_types ON pets.type = pet_types.id
        JOIN users ON users.id = owners.owner_id
        WHERE owner_id = ?
        ORDER BY pets.created DESC, pets.id DESC
        """,
        (user_id,),
    ).fetchall()


def auth_limit_key():
    ip = get_remote_address() or "unknown"
    username = (request.form.get("username") or "").strip().lower()
    return f"{ip}:{username or 'anonymous'}"


def password_limit_key():
    ip = get_remote_address() or "unknown"
    user_id = session_get_int("user_id")
    return f"{ip}:{user_id or 'anonymous'}"

@app.route("/")
def index():
    """Landing page for visitors, dashboard for registered users"""
    if (session_get_int("user_id") is not None):
        progress = get_learning_progress(session_get_int("user_id"))
        return render_template("dashboard.html", progress=progress)
    else:
        return render_template("index.html")


@app.route("/quests")
@login_required
def quests():
    """Quest board showing available and locked quest lines."""
    user_id = session_get_int("user_id")
    locale = get_learning_language_charcode(user_id)

    board_entries = get_quest_board_entries(user_id, locale=locale)
    active_pet = session.get("active_pet") or get_active_pet_for_user(user_id)

    available_quests = [quest for quest in board_entries if quest["state"] == "available"]
    locked_quests = [quest for quest in board_entries if quest["state"] == "locked"]
    switchable_quests = [quest for quest in locked_quests if quest.get("switchable")]
    featured_quest = available_quests[0] if available_quests else None

    return render_template(
        "quests.html",
        active_pet=active_pet,
        available_quests=available_quests,
        locked_quests=locked_quests,
        switchable_quests=switchable_quests,
        featured_quest=featured_quest,
    )


@app.route("/quest/<quest_id>")
@adopted_pet_required
def quest_detail(quest_id):
    """Quest detail page with story and quiz content."""
    user_id = session_get_int("user_id")
    locale = get_learning_language_charcode(user_id)

    can_access, reason = can_user_access_quest(user_id, quest_id, locale=locale)
    if not can_access:
        if reason == "no_active_pet":
            flash("Adopt a pet first to start quests.")
            return redirect("/adopt")
        flash("That quest is locked for your current pet.")
        return redirect("/quests")

    active_pet = session.get("active_pet") or get_active_pet_for_user(user_id) or {}
    quest = load_and_personalize_quest(
        quest_id,
        locale=locale,
        gender=active_pet.get("gender", "neutral") or "neutral",
        pet_name=active_pet.get("name"),
    )

    return render_template("quest.html", quest=quest, active_pet=active_pet)


@app.route("/quest/<quest_id>/<episode_id>")
@adopted_pet_required
def quest_episode(quest_id, episode_id):
    """Quest episode detail page showing story and sentences for a single episode."""
    user_id = session_get_int("user_id")
    locale = get_learning_language_charcode(user_id)

    can_access, reason = can_user_access_quest(user_id, quest_id, locale=locale)
    if not can_access:
        if reason == "no_active_pet":
            flash("Adopt a pet first to start quests.")
            return redirect("/adopt")
        flash("That quest is locked for your current pet.")
        return redirect("/quests")

    active_pet = session.get("active_pet") or get_active_pet_for_user(user_id) or {}
    
    try:
        quest_metadata, episode = load_episode_from_quest(
            quest_id,
            episode_id,
            locale=locale,
            gender=active_pet.get("gender", "neutral") or "neutral",
            pet_name=active_pet.get("name"),
        )
    except ValueError as e:
        flash(str(e))
        return redirect(f"/quest/{quest_id}")

    # Enforce sequential episode access: require previous episode completion
    prev_ep = episode.get("previous_episode_id")
    if prev_ep and not has_completed_episode(session_get_int("user_id"), quest_id, prev_ep):
        flash("This episode is locked. Complete the previous episode to unlock.")
        return redirect(f"/quest/{quest_id}/{prev_ep}")
    
    # Get vocabulary with translations
    vocabulary_with_translations = []
    episode_targets = episode.get("resolved_vocabulary_target_ids") or episode.get("vocabulary_target_ids") or episode.get("vocabulary_targets")
    if episode_targets:
        learning_lang_id = session.get("language", {}).get("learning")
        preferred_lang_id = session.get("language", {}).get("preferred")
        if learning_lang_id and preferred_lang_id:
            vocabulary_with_translations = get_vocabulary_with_translations(
                episode_targets,
                learning_lang_id,
                preferred_lang_id
            )

    return render_template(
        "quest_episode.html",
        quest_metadata=quest_metadata,
        episode=episode,
        active_pet=active_pet,
        vocabulary_with_translations=vocabulary_with_translations
    )


def _normalize_quiz_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _parse_reorder_submission(value):
    if not value:
        return []
    try:
        return [int(part) for part in str(value).split(",") if str(part).strip() != ""]
    except (TypeError, ValueError):
        return []


def _grade_quiz_submission(questions, form_data):
    results = []
    correct_count = 0

    for question_index, question in enumerate(questions):
        q_type = question.get("type")
        submitted_value = form_data.get(f"answer_{question_index}", "")
        is_correct = False

        if q_type == "cloze":
            accepted_answers = question.get("accepted_answers")
            if not isinstance(accepted_answers, list) or not accepted_answers:
                accepted_answers = [question.get("answer")]
            normalized_submission = _normalize_quiz_text(submitted_value)
            is_correct = any(
                normalized_submission == _normalize_quiz_text(answer)
                for answer in accepted_answers
                if answer is not None
            )

        elif q_type == "multiple_choice":
            is_correct = _normalize_quiz_text(submitted_value) == _normalize_quiz_text(question.get("answer"))

        elif q_type == "count_sequence":
            selected_index = None
            try:
                selected_index = int(submitted_value)
            except (TypeError, ValueError):
                selected_index = None

            options = question.get("options")
            answer = question.get("answer")
            if isinstance(options, list) and isinstance(answer, list) and selected_index is not None:
                if 0 <= selected_index < len(options):
                    selected_option = options[selected_index]
                    if isinstance(selected_option, list):
                        is_correct = [str(item) for item in selected_option] == [str(item) for item in answer]

        elif q_type == "reorder":
            correct_order = question.get("correct_order")
            submitted_order = _parse_reorder_submission(submitted_value)
            if isinstance(correct_order, list):
                try:
                    expected_order = [int(item) for item in correct_order]
                except (TypeError, ValueError):
                    expected_order = []
                is_correct = submitted_order == expected_order

        if is_correct:
            correct_count += 1

        results.append({
            "index": question_index,
            "type": q_type,
            "correct": is_correct,
        })

    return {
        "correct": correct_count,
        "total": len(questions),
        "results": results,
    }


QUIZ_MAX_STEPS = 7
QUIZ_SESSION_PREFIX = "quiz_wizard"


def _quiz_state_key(quest_id, episode_id):
    return f"{QUIZ_SESSION_PREFIX}:{quest_id}:{episode_id}"


def _tokenize_sentence_text(sentence_text):
    """ 
    Tokenize sentence text for sentence-building quiz steps.
    This function removes punctuation and splits on whitespace, 
    while preserving the original tokens for display.
    """
    if not sentence_text:
        return []
    cleaned_chars = []
    for char in str(sentence_text).strip():
        if unicodedata.category(char)[0] in {"P", "S"}:
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(char)
    cleaned_text = "".join(cleaned_chars)
    return [token for token in re.split(r"\s+", cleaned_text) if token]


def _build_quiz_step_pool(episode, seed, translation_episode=None, vocabulary_translation_map=None):
    """
    Build a randomized pool of quiz steps for the episode, 
    combining quiz questions and sentence-building tasks.
    """
    rng = random.Random(seed)

    raw_questions = []
    if isinstance(episode.get("quiz"), dict):
        candidate_questions = episode["quiz"].get("questions", [])
        if isinstance(candidate_questions, list):
            raw_questions = [question for question in candidate_questions if isinstance(question, dict)]

    sentence_refs = [
        sentence
        for sentence in episode.get("story_sentence_refs", [])
        if isinstance(sentence, dict)
        and isinstance(sentence.get("id"), str)
        and sentence.get("id").strip()
        and isinstance(sentence.get("text"), str)
        and sentence.get("text").strip()
    ]

    translation_sentence_refs = {}
    if isinstance(translation_episode, dict):
        for sentence in translation_episode.get("story_sentence_refs", []):
            if not isinstance(sentence, dict):
                continue
            sentence_id = sentence.get("id")
            sentence_text = sentence.get("text")
            if isinstance(sentence_id, str) and sentence_id.strip() and isinstance(sentence_text, str) and sentence_text.strip():
                translation_sentence_refs[sentence_id] = sentence_text

    vocabulary_translation_map = vocabulary_translation_map or {}

    total_available = len(raw_questions) + len(sentence_refs)
    total_target = min(QUIZ_MAX_STEPS, total_available)
    if total_target <= 0:
        return []

    # Aim for a balanced mix of question types, 
    # but allow flexibility based on availability
    quiz_target = min((QUIZ_MAX_STEPS + 1) // 2, len(raw_questions))
    sentence_target = min(total_target - quiz_target, len(sentence_refs))

    remaining = total_target - (quiz_target + sentence_target)
    if remaining > 0:
        extra_quiz = min(remaining, len(raw_questions) - quiz_target)
        quiz_target += extra_quiz
        remaining -= extra_quiz
        if remaining > 0:
            sentence_target += min(remaining, len(sentence_refs) - sentence_target)

    question_indices = list(range(len(raw_questions)))
    sentence_indices = list(range(len(sentence_refs)))
    rng.shuffle(question_indices)
    rng.shuffle(sentence_indices)

    selected_question_indices = question_indices[:quiz_target]
    selected_sentence_indices = sentence_indices[:sentence_target]

    # Build a pool of step data dicts that can be rendered in the quiz wizard,
    # randomized but with all necessary context for grading and feedback 
    # stored in the step data.
    step_pool = []

    for source_index in selected_question_indices:
        question = raw_questions[source_index]
        sentence_text = None
        sentence_id = question.get("sentence_id")
        answer_text = question.get("answer") or ""

        # First try to get translation from the vocabulary map, 
        # then fall back to sentence-level translation if 
        # it's linked to a sentence
        answer_translation = vocabulary_translation_map.get(answer_text, "")
        if isinstance(sentence_id, str) and sentence_id.strip():
            for ref in sentence_refs:
                if ref.get("id") == sentence_id:
                    sentence_text = ref.get("text")
                    break

        if not answer_translation and isinstance(sentence_id, str) and sentence_id.strip():
            answer_translation = translation_sentence_refs.get(sentence_id, "")

        step_pool.append({
            "kind": "quiz",
            "source_index": source_index,
            "step_type": question.get("type"),
            "question": question,
            "prompt": question.get("prompt"),
            "source_sentence": sentence_text,
            "correct_answer": answer_text,
            "correct_answer_translation": answer_translation,
            "summary_prompt": question.get("prompt") or sentence_text or question.get("answer") or "Quiz question",
        })

    for source_index in selected_sentence_indices:
        sentence_ref = sentence_refs[source_index]
        sentence_text = sentence_ref.get("text") or ""
        token_entries = [
            {"index": idx, "text": token}
            for idx, token in enumerate(_tokenize_sentence_text(sentence_text))
        ]
        shuffled_tokens = token_entries[:]
        rng.shuffle(shuffled_tokens)

        step_pool.append({
            "kind": "sentence",
            "source_index": source_index,
            "sentence_id": sentence_ref.get("id"),
            "sentence_text": sentence_text,
            "correct_answer_translation": translation_sentence_refs.get(sentence_ref.get("id"), ""),
            "sentence_tokens": token_entries,
            "shuffled_tokens": shuffled_tokens,
            "summary_prompt": sentence_text or "Sentence building",
            "correct_answer": sentence_text,
        })

    rng.shuffle(step_pool)

    for step_number, step in enumerate(step_pool, start=1):
        step["step_number"] = step_number
        step["attempts"] = 0
        step["awaiting_review"] = False
        step["hint_revealed"] = False
        step["completed"] = False
        step["first_try_correct"] = False
        step["earned_point"] = False
        step["submitted_answer"] = ""

    return step_pool


def _create_quiz_state(quest_id, episode_id, episode, translation_episode=None, vocabulary_translation_map=None):
    seed = secrets.randbits(32)
    step_pool = _build_quiz_step_pool(episode, seed, translation_episode=translation_episode, vocabulary_translation_map=vocabulary_translation_map)
    if not step_pool:
        return None

    return {
        "quest_id": quest_id,
        "episode_id": episode_id,
        "seed": seed,
        "current_step": 0,
        "score": 0,
        "finished": False,
        "recorded_completion": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": step_pool,
    }


def _grade_quiz_step(step, form_data):
    submitted_answer = ""
    correct_answer = step.get("correct_answer") or ""
    is_correct = False

    if step.get("kind") == "sentence":
        submitted_order = _parse_reorder_submission(form_data.get("answer_order"))
        expected_order = [token.get("index") for token in step.get("sentence_tokens", [])]
        submitted_tokens = []
        for token_index in submitted_order:
            try:
                token = step.get("sentence_tokens", [])[int(token_index)]
            except (IndexError, TypeError, ValueError):
                token = None
            if token is not None:
                submitted_tokens.append(token.get("text", ""))
        submitted_answer = " ".join(token for token in submitted_tokens if token)
        is_correct = submitted_order == expected_order

    else:
        question = step.get("question") if isinstance(step.get("question"), dict) else {}
        q_type = step.get("step_type")
        submitted_value = form_data.get("answer", "")
        submitted_answer = submitted_value

        if q_type == "cloze":
            accepted_answers = question.get("accepted_answers")
            if not isinstance(accepted_answers, list) or not accepted_answers:
                accepted_answers = [question.get("answer")]
            normalized_submission = _normalize_quiz_text(submitted_value)
            is_correct = any(
                normalized_submission == _normalize_quiz_text(answer)
                for answer in accepted_answers
                if answer is not None
            )
            if is_correct and accepted_answers:
                correct_answer = accepted_answers[0] or ""

        elif q_type == "multiple_choice":
            correct_answer = question.get("answer") or ""
            is_correct = _normalize_quiz_text(submitted_value) == _normalize_quiz_text(correct_answer)

        elif q_type == "count_sequence":
            selected_index = None
            try:
                selected_index = int(submitted_value)
            except (TypeError, ValueError):
                selected_index = None

            options = question.get("options")
            answer = question.get("answer")
            if isinstance(options, list) and isinstance(answer, list) and selected_index is not None:
                if 0 <= selected_index < len(options):
                    selected_option = options[selected_index]
                    if isinstance(selected_option, list):
                        is_correct = [str(item) for item in selected_option] == [str(item) for item in answer]
                        if is_correct:
                            correct_answer = ", ".join(str(item) for item in answer)

        elif q_type == "reorder":
            correct_order = question.get("correct_order")
            submitted_order = _parse_reorder_submission(submitted_value)
            if isinstance(correct_order, list):
                try:
                    expected_order = [int(item) for item in correct_order]
                except (TypeError, ValueError):
                    expected_order = []
                is_correct = submitted_order == expected_order
                if is_correct:
                    correct_answer = ",".join(str(item) for item in expected_order)

    return {
        "correct": is_correct,
        "submitted_answer": submitted_answer,
        "correct_answer": correct_answer,
    }


def _build_quiz_results(state):
    results = []
    for step in state.get("steps", []):
        results.append({
            "step_number": step.get("step_number"),
            "kind": step.get("kind"),
            "prompt": step.get("summary_prompt") or step.get("source_sentence") or step.get("correct_answer") or "",
            "earned_point": bool(step.get("earned_point")),
            "status_text": "Correct" if step.get("earned_point") else "Incorrect",
            "submitted_answer": step.get("submitted_answer") or "",
            "correct_answer": step.get("correct_answer") or "",
            "correct_answer_translation": step.get("correct_answer_translation") or "",
            "first_try_correct": bool(step.get("first_try_correct")),
        })
    return results


@app.route("/quiz/<quest_id>/<episode_id>")
@adopted_pet_required
def quiz_episode(quest_id, episode_id):
    """Quiz page for a specific episode - now rendered as a sequential wizard."""
    user_id = session_get_int("user_id")
    locale = get_learning_language_charcode(user_id)

    can_access, reason = can_user_access_quest(user_id, quest_id, locale=locale)
    if not can_access:
        if reason == "no_active_pet":
            flash("Adopt a pet first to start quests.")
            return redirect("/adopt")
        flash("That quest is locked for your current pet.")
        return redirect("/quests")

    active_pet = session.get("active_pet") or get_active_pet_for_user(user_id) or {}
    
    try:
        quest_metadata, episode = load_episode_from_quest(
            quest_id,
            episode_id,
            locale=locale,
            gender=active_pet.get("gender", "neutral") or "neutral",
            pet_name=active_pet.get("name"),
        )
    except ValueError as e:
        flash(str(e))
        return redirect(f"/quest/{quest_id}")

    translation_episode = None
    vocabulary_translation_map = {}
    if locale != "en":
        try:
            _, translation_episode = load_episode_from_quest(
                quest_id,
                episode_id,
                locale="en",
                gender=active_pet.get("gender", "neutral") or "neutral",
                pet_name=active_pet.get("name"),
            )
        except ValueError:
            translation_episode = None

    episode_targets = episode.get("resolved_vocabulary_target_ids") or episode.get("vocabulary_target_ids") or episode.get("vocabulary_targets")
    if episode_targets:
        learning_lang_id = session.get("language", {}).get("learning")
        preferred_lang_id = session.get("language", {}).get("preferred")
        if learning_lang_id and preferred_lang_id:
            vocabulary_with_translations = get_vocabulary_with_translations(
                episode_targets,
                learning_lang_id,
                preferred_lang_id,
            )
            for vocab in vocabulary_with_translations:
                word = vocab.get("word")
                translation = vocab.get("translation")
                if word and translation:
                    vocabulary_translation_map[word] = translation

    # Enforce sequential episode access for quizzes as well
    prev_ep = episode.get("previous_episode_id")
    if prev_ep and not has_completed_episode(session_get_int("user_id"), quest_id, prev_ep):
        flash("This episode is locked. Complete the previous episode to unlock.")
        return redirect(f"/quest/{quest_id}/{prev_ep}")

    state_key = _quiz_state_key(quest_id, episode_id)
    restart_requested = request.args.get("restart") == "1"
    state = session.get(state_key)
    if restart_requested or not isinstance(state, dict) or state.get("quest_id") != quest_id or state.get("episode_id") != episode_id:
        state = _create_quiz_state(
            quest_id,
            episode_id,
            episode,
            translation_episode=translation_episode,
            vocabulary_translation_map=vocabulary_translation_map,
        )
        if state is None:
            flash("No quiz steps found for this episode.")
            return redirect(f"/quest/{quest_id}/{episode_id}")
        # Ensure any missing step translations are populated from the English translation episode
        if isinstance(state, dict) and isinstance(translation_episode, dict):
            try:
                trans_map = {
                    s.get("id"): s.get("text")
                    for s in translation_episode.get("story_sentence_refs", [])
                    if isinstance(s, dict) and s.get("id")
                }
                for step in state.get("steps", []):
                    if not step.get("correct_answer_translation"):
                        sid = None
                        if step.get("kind") == "sentence":
                            sid = step.get("sentence_id")
                        else:
                            q = step.get("question") or {}
                            sid = q.get("sentence_id") if isinstance(q, dict) else None
                        if sid and sid in trans_map:
                            step["correct_answer_translation"] = trans_map.get(sid)
            except Exception:
                # Best-effort only; do not break quiz initialization on unexpected errors
                pass
        session[state_key] = state

    steps = state.get("steps", []) if isinstance(state, dict) else []
    if not isinstance(steps, list) or not steps:
        flash("No quiz steps found for this episode.")
        return redirect(f"/quest/{quest_id}/{episode_id}")

    current_step_index = int(state.get("current_step", 0) or 0)
    if current_step_index < 0:
        current_step_index = 0
    if current_step_index >= len(steps):
        state["finished"] = True
        session[state_key] = state

    next_episode_url = None
    if state.get("finished") and episode.get("has_next") and episode.get("next_episode_id"):
        next_episode_url = f"/quest/{quest_id}/{episode.get('next_episode_id')}"

    quiz_results = _build_quiz_results(state)
    quiz_step = None
    if not state.get("finished"):
        quiz_step = steps[current_step_index]
        if not quiz_step.get("completed"):
            quiz_step["show_correct_feedback"] = False

    return render_template(
        "quiz.html",
        quest_metadata=quest_metadata,
        episode=episode,
        active_pet=active_pet,
        quiz_state={
            "current_step": current_step_index,
            "total_steps": len(steps),
            "score": state.get("score", 0),
            "finished": bool(state.get("finished")),
        },
        quiz_step=quiz_step,
        quiz_results=quiz_results,
        next_episode_url=next_episode_url,
    )


@app.route("/quiz/<quest_id>/<episode_id>/submit", methods=["POST"])
@adopted_pet_required
def quiz_episode_submit(quest_id, episode_id):
    """Advance or review a single quiz step in the quiz wizard."""
    user_id = session_get_int("user_id")
    locale = get_learning_language_charcode(user_id)

    can_access, reason = can_user_access_quest(user_id, quest_id, locale=locale)
    if not can_access:
        if reason == "no_active_pet":
            flash("Adopt a pet first to start quests.")
            return redirect("/adopt")
        flash("That quest is locked for your current pet.")
        return redirect("/quests")

    active_pet = session.get("active_pet") or get_active_pet_for_user(user_id) or {}

    try:
        quest_metadata, episode = load_episode_from_quest(
            quest_id,
            episode_id,
            locale=locale,
            gender=active_pet.get("gender", "neutral") or "neutral",
            pet_name=active_pet.get("name"),
        )
    except ValueError as e:
        flash(str(e))
        return redirect(f"/quest/{quest_id}")

    state_key = _quiz_state_key(quest_id, episode_id)
    state = session.get(state_key)
    if not isinstance(state, dict) or state.get("quest_id") != quest_id or state.get("episode_id") != episode_id:
        state = _create_quiz_state(quest_id, episode_id, episode)
        if state is None:
            flash("No quiz steps found for this episode.")
            return redirect(f"/quiz/{quest_id}/{episode_id}")
        session[state_key] = state

    steps = state.get("steps", [])
    if not isinstance(steps, list) or not steps:
        flash("No quiz steps found for this episode.")
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    current_step_index = int(state.get("current_step", 0) or 0)
    if current_step_index < 0 or current_step_index >= len(steps):
        state["finished"] = True
        session[state_key] = state
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    current_step = steps[current_step_index]
    action = request.form.get("action", "submit")

    if action == "next":
        if current_step.get("completed"):
            current_step["show_correct_feedback"] = False
            current_step["pending_next"] = False
            current_step["hint_revealed"] = False
            current_step["awaiting_review"] = False
            state["current_step"] = current_step_index + 1
            if state["current_step"] >= len(steps):
                state["finished"] = True
                if not state.get("recorded_completion"):
                    first_time = record_episode_completed(user_id, quest_id, episode_id)
                    if first_time and state.get("score", 0) > 0:
                        update_experience(state["score"])
                    state["recorded_completion"] = True
            session[state_key] = state
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    if action == "hint":
        current_step["hint_revealed"] = True
        current_step["awaiting_review"] = True
        session[state_key] = state
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    if action == "retry":
        current_step["hint_revealed"] = False
        current_step["awaiting_review"] = False
        session[state_key] = state
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    if action == "forfeit":
        session.pop(state_key, None)
        return redirect(f"/quest/{quest_id}")

    if current_step.get("awaiting_review") and not current_step.get("hint_revealed"):
        flash("Review the context before retrying this step.")
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    submission = _grade_quiz_step(current_step, request.form)
    current_step["submitted_answer"] = submission["submitted_answer"]
    current_step["correct_answer"] = submission["correct_answer"] or current_step.get("correct_answer") or ""

    if submission["correct"]:
        first_try = int(current_step.get("attempts", 0) or 0) == 0
        current_step["completed"] = True
        current_step["first_try_correct"] = first_try
        current_step["earned_point"] = first_try
        current_step["awaiting_review"] = False
        current_step["hint_revealed"] = False
        current_step["show_correct_feedback"] = True
        current_step["pending_next"] = True
        if first_try:
            state["score"] = int(state.get("score", 0) or 0) + 1
        session[state_key] = state
        return redirect(f"/quiz/{quest_id}/{episode_id}")

    current_step["attempts"] = int(current_step.get("attempts", 0) or 0) + 1
    current_step["first_try_correct"] = False if current_step["attempts"] == 1 else current_step.get("first_try_correct", False)
    current_step["earned_point"] = False
    current_step["awaiting_review"] = True
    current_step["hint_revealed"] = False
    session[state_key] = state
    return redirect(f"/quiz/{quest_id}/{episode_id}")


@app.route("/pets")
@login_required
def pets():
    """Lists all of user's pets"""
    
    pet_columns = table_columns("pets")
    gender_column = ", pets.gender" if "gender" in pet_columns else ""
    pets_owned = db.execute(f"SELECT pets.id, pet_types.imgsrc, pet_types.pet_type, pets.created, pets.exp, pets.name{gender_column}, users.active_pet_id FROM owners JOIN pets ON pets.id = owners.pet_id JOIN pet_types ON pets.type = pet_types.id JOIN users ON users.id = owners.owner_id WHERE owner_id = ?", (session_get_int("user_id"), )).fetchall()
    pets_owned = [
        {
            **dict(pet),
            "gender": dict(pet).get("gender") or "neutral",
            "gender_label": get_pet_gender_label(dict(pet).get("gender")),
            "gender_icon_class": get_pet_gender_icon_class(dict(pet).get("gender")),
        }
        for pet in pets_owned
    ]
    return render_template("list.html", pets_owned=pets_owned)


@app.route("/train")
@adopted_pet_required
def train():
    """Lists available word sets to learn and test on"""
    role = get_role()
    sets = get_sets()
    return render_template("train.html", sets=sets, role=role)


@app.route("/train/set/")
@adopted_pet_required
def trainset():
    """Allows a user to learn a set of words, one word at a time"""
    tset = int(request.args.get('s'))
    page = 0
    if request.args.get('page') is not None:
        page = int(request.args.get('page'))
    if tset is not None:
        words = get_words_by_set_id(tset)
        set_info = db.execute(
            "SELECT id, imgsrc FROM word_sets WHERE id = ?", (tset, )).fetchall()
        return render_template("trainset.html", words=words, set_info=set_info, page=page, tset=tset)
    else:
        return redirect('/train')


@app.route("/edit/set/")
@login_required
@admin_required
def edit_set():
    """Admin: Allows an admin to edit word sets"""
    role = get_role()
    if request.args.get('set_id') is not None:
        set_id = int(request.args.get('set_id'))
        set_info = get_set_by_id(set_id)
        words = get_words_by_set_id(set_id)
        sets = get_sets(session.get('language')[
                        'learning'], session.get('language')['preferred'])
        return render_template("editset.html", set_info=set_info, role=role, words=words, sets=sets)
    else:
        sets = get_sets()
        return render_template("editsets.html", sets=sets, role=role)


@app.route("/edit/word/", methods=["GET", "POST"])
@login_required
@admin_required
def edit_word():
    """Admin: Backward-compatible redirect to canonical admin vocabulary edit."""
    word_id = request.values.get("word_id")
    if not word_id:
        flash("Missing word id")
        return redirect("/admin/vocabulary/")

    canonical_sense_id = resolve_canonical_sense_id(word_id)
    if canonical_sense_id is not None:
        lemma_row = db.execute(
            "SELECT lemma_id FROM sense WHERE id = ? LIMIT 1",
            (int(canonical_sense_id),),
        ).fetchone()
        if lemma_row is not None:
            return redirect(f"/admin/vocabulary/edit/{int(lemma_row['lemma_id'])}/")

    flash("Word not found in canonical vocabulary.")
    return redirect("/admin/vocabulary/")


@app.route("/quiz/set/", methods=["GET", "POST"])
@adopted_pet_required
def quizset():
    """Shows a quiz for a given set of words, one word at a time. Experience is added on completion."""
    if request.method == "POST":

        experience = 0
        if request.form.get('experience') is not None:
            experience = int(request.form.get('experience'))

        if request.form.get("finished"):
            # Process exp
            if (experience > 0):
                # Add experience to active pet
                update_experience(experience)
                set_id = int(request.form.get('set_id')) if request.form.get("set_id") else None
                if set_id is not None:
                    words = get_words_by_set_id(set_id)
                    if experience >= len(words):
                        set_info = get_set_by_id(set_id)
                        learned_id = record_set_learned(session_get_int("user_id"), set_id, subject=set_info["wordstr"])
                        record_words_learned(session_get_int("user_id"), learned_id, [int(word["id"]) for word in words])
                flash("Gained " + str(experience) + " experience!")
            return redirect('/train')

        elif request.form.get("set_id"):
            set_id = int(request.form.get('set_id'))
            page = 0

            if request.form.get('page') is not None:
                page = int(request.form.get('page'))
            if set_id is not None:
                words = get_words_by_set_id(int(set_id))
                set_info = db.execute(
                    "SELECT id, imgsrc FROM word_sets WHERE id = ?", (set_id, )).fetchall()

                activeword = words[page]
                word_options = []
                # Pull alternate word choices
                for w in words:
                    # Don't duplicate answer word
                    if w['id'] != activeword['id']:
                        word_options.append({
                            'word': get_word_translation(w['id']),
                            'data': 'error',
                            'translation': w['wordstr']
                        })

                # Shuffle and limit alternate answers to 3
                random.shuffle(word_options)
                if (len(word_options) > 3):
                    word_options = word_options[0:3]

                # Add correct answer to the array of answers
                word_options.append({
                    'word': get_word_translation(activeword['id']),
                    'data': 'success',
                    'translation': activeword['wordstr']
                })
                random.shuffle(word_options)

                return render_template("quizset.html", words=words, word_options=word_options, set_info=set_info, page=page, set_id=set_id, experience=experience)
        else:
            return redirect('/train')

    # GET
    else:
        return redirect('/train')


@app.route("/create/set/", methods=["GET", "POST"])
@login_required
@admin_required
def createset():
    """Admin: Allows an admin to create a new set"""

    if request.method == "POST":
        if request.form.get('setname') is not None:

            setname = request.form.get('setname')
            learning_lang = int(request.form.get('learning_lang'))
            plang_setname = request.form.get('plang_setname')
            preferred_lang = int(request.form.get('preferred_lang'))

            language_rows = db.execute(
                "SELECT id, charcode FROM languages WHERE id IN (?, ?)",
                (learning_lang, preferred_lang),
            ).fetchall()
            lang_code_map = {int(row['id']): (row['charcode'] or '') for row in language_rows}

            learning_lemma_id = db.execute(
                "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
                (learning_lang, 1, '', None),
            ).lastrowid
            db.execute(
                "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    learning_lemma_id,
                    learning_lang,
                    'surface',
                    'Hebr' if lang_code_map.get(learning_lang, '').lower() == 'he' else 'Latn',
                    setname,
                    compute_search_key(setname, lang_code_map.get(learning_lang, '')),
                    1,
                ),
            )
            learning_sense_id = db.execute(
                "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
                (learning_lemma_id, 1, 1),
            ).lastrowid

            preferred_lemma_id = db.execute(
                "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
                (preferred_lang, 1, '', None),
            ).lastrowid
            db.execute(
                "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    preferred_lemma_id,
                    preferred_lang,
                    'surface',
                    'Hebr' if lang_code_map.get(preferred_lang, '').lower() == 'he' else 'Latn',
                    plang_setname,
                    compute_search_key(plang_setname, lang_code_map.get(preferred_lang, '')),
                    1,
                ),
            )
            preferred_sense_id = db.execute(
                "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
                (preferred_lemma_id, 1, 1),
            ).lastrowid

            db.execute(
                "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
                (preferred_sense_id, learning_sense_id, 'exact'),
            )
            db.execute(
                "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
                (learning_sense_id, preferred_sense_id, 'exact'),
            )

            # TODO: Default image for sets, or allow upload during set creation
            insert_word_set = db.execute(
                "INSERT INTO word_sets (imgsrc, set_name_word_id, language_id, set_name_sense_id) VALUES (?, ?, ?, ?)",
                ("/sets/fruits.png", None, learning_lang, learning_sense_id),
            ).lastrowid
            insert_word_set_orig = db.execute(
                "INSERT INTO word_sets (imgsrc, set_name_word_id, language_id, set_name_sense_id) VALUES (?, ?, ?, ?)",
                ("/sets/fruits.png", None, preferred_lang, preferred_sense_id),
            ).lastrowid
            con.commit()

            if (insert_word_set > 0):
                flash("New set created: " + setname)
            if (insert_word_set_orig > 0):
                flash("New set created: " + plang_setname)

            else:
                flash("Error creating new set")
            sets = get_sets()
        return render_template("editsets.html", sets=sets)
    else:
        language_options = db.execute("SELECT * FROM languages").fetchall()
        userinfo = db.execute(
            "SELECT username, id, preferred_lang, learning_lang, created_at, email, full_name FROM users WHERE id = ?", (session_get_int("user_id"), )).fetchall()
        return render_template("createset.html", language_options=language_options, userinfo=userinfo[0])


@app.route("/delete/word_set_word/", methods=["POST"])
@login_required
@admin_required
def delete_word():
    """Admin: Deletes word from word set only"""

    if request.method == "POST":
        if request.form.get('word_id') is not None:
            if request.form.get('word_set_id') is not None:
                canonical_sense_id = resolve_canonical_sense_id(request.form.get("word_id"))
                deleteqry = None
                if canonical_sense_id is not None:
                    deleteqry = db.execute(
                        "DELETE FROM set_item WHERE sense_id = ? and word_set_id = ?",
                        (canonical_sense_id, request.form.get("word_set_id")),
                    )
                con.commit()
                if deleteqry is not None and (deleteqry.rowcount > 0):
                    flash('delete successful')
    return redirect("/edit/set")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute", key_func=auth_limit_key)
def login():
    """Log user in"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password")

        if not username:
            return apology("must provide username", 403)
        elif not password:
            return apology("must provide password", 403)
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          (username, )).fetchall()
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], password):
            return apology("invalid username and/or password", 403)

        session["user_id"] = int(rows[0]["id"])
        session["username"] = username

        set_active_pet_in_session(session_get_int("user_id"))
        set_languages(session_get_int("user_id"))
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/admin/", methods=["GET"])
@login_required
@admin_required
def admin_home():
    """Admin landing page."""
    summary = {
        "lemmas": db.execute("SELECT COUNT(*) AS count FROM lemma").fetchone()["count"],
        "senses": db.execute("SELECT COUNT(*) AS count FROM sense").fetchone()["count"],
        "sets": db.execute("SELECT COUNT(*) AS count FROM word_sets").fetchone()["count"],
    }
    return render_template("admin/index.html", summary=summary)


@app.route("/admin/vocabulary/", methods=["GET"])
@login_required
@admin_required
def admin_vocabulary():
    """Admin: Vocabulary list (canonical lemma view).

    Supports server-side pagination, basic search, and rows-per-page selection.
    """
    page = int(request.args.get('page') or 1)
    per_page = int(request.args.get('per_page') or 20)
    search = (request.args.get('q') or '').strip()
    language_id = int(request.args.get('language_id') or 0)
    pos_id = int(request.args.get('pos_id') or 0)
    status = (request.args.get('status') or '').strip().lower()
    sort = (request.args.get('sort') or 'name-asc').strip().lower()

    offset = (page - 1) * per_page

    # Detect schema features at runtime so admin UI is resilient across environments
    pragma = db.execute("PRAGMA table_info(lemma)").fetchall()
    cols = [r['name'] for r in pragma]
    has_image = 'image_path' in cols
    has_state = 'state' in cols

    image_select = "l.image_path AS image_path" if has_image else "NULL AS image_path"
    state_select = "l.state AS state" if has_state else "'published' AS state"
    preferred_lang_id = session.get("language", {}).get("preferred") or 1
    translation_select = f"""
        (
            SELECT lf2.value
            FROM sense s
            JOIN sense_translation st ON st.source_sense_id = s.id
            JOIN sense s2 ON s2.id = st.target_sense_id
            JOIN lemma_form lf2 ON lf2.lemma_id = s2.lemma_id
            WHERE s.lemma_id = l.id
              AND s.is_primary = 1
              AND lf2.language_id = ?
              AND lf2.is_primary = 1
            LIMIT 1
        ) AS translation
    """

    base_sql = f"""
        SELECT l.id AS lemma_id,
               lf.value AS lemma_value,
               {image_select},
               {state_select},
               {translation_select},
               COALESCE(ll.charcode, '') AS lang_code,
               COALESCE(ll.name, '') AS language_name,
               CASE l.pos_id WHEN 1 THEN 'noun' WHEN 2 THEN 'verb' WHEN 3 THEN 'adj' ELSE CAST(l.pos_id AS TEXT) END AS pos_label,
               (SELECT COUNT(*) FROM set_item si JOIN sense s ON s.id = si.sense_id WHERE s.lemma_id = l.id) AS uses
        FROM lemma l
        JOIN lemma_form lf ON lf.lemma_id = l.id AND lf.is_primary = 1
        LEFT JOIN languages ll ON ll.id = l.language_id
    """

    params = [preferred_lang_id]
    where_clauses = []
    if search:
        where_clauses.append(
            "(" \
            "LOWER(lf.value) LIKE LOWER(?) OR " \
            "EXISTS (SELECT 1 FROM lemma_form lf_search WHERE lf_search.lemma_id = l.id AND LOWER(lf_search.value) LIKE LOWER(?)) OR " \
            "EXISTS (SELECT 1 FROM sense s_search JOIN sense_translation st_search ON st_search.source_sense_id = s_search.id JOIN sense s_target ON s_target.id = st_search.target_sense_id JOIN lemma_form lf_target ON lf_target.lemma_id = s_target.lemma_id WHERE s_search.lemma_id = l.id AND lf_target.language_id = ? AND LOWER(lf_target.value) LIKE LOWER(?))" \
            ")"
        )
        params.extend([f"%{search}%", f"%{search}%", preferred_lang_id, f"%{search}%"])
    if language_id:
        where_clauses.append("l.language_id = ?")
        params.append(language_id)
    if pos_id:
        where_clauses.append("l.pos_id = ?")
        params.append(pos_id)
    if has_state and status in {"published", "draft", "review", "approved", "archived"}:
        where_clauses.append("l.state = ?")
        params.append(status)

    if where_clauses:
        base_sql += " WHERE " + " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS count FROM ({base_sql})"
    total = db.execute(count_sql, params).fetchone()["count"]

    sort_clauses = {
        "name-asc": "lf.value COLLATE NOCASE ASC",
        "name-desc": "lf.value COLLATE NOCASE DESC",
        "recent": "l.id DESC",
        "status": "l.state ASC, lf.value COLLATE NOCASE ASC",
    }
    order_by = sort_clauses.get(sort, sort_clauses["name-asc"])
    if sort == "status" and not has_state:
        order_by = sort_clauses["name-asc"]

    page_sql = base_sql + f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    rows = db.execute(page_sql, params).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)

    filter_params = {}
    if search:
        filter_params["q"] = search
    if language_id:
        filter_params["language_id"] = language_id
    if pos_id:
        filter_params["pos_id"] = pos_id
    if has_state and status:
        filter_params["status"] = status
    if sort and sort != "name-asc":
        filter_params["sort"] = sort
    if per_page != 20:
        filter_params["per_page"] = per_page

    pagination_query = urlencode(filter_params)

    languages = db.execute("SELECT id, name, charcode FROM languages ORDER BY name ASC").fetchall()
    pos_options = db.execute("SELECT id, type FROM word_type ORDER BY type ASC").fetchall()

    return render_template(
        "admin/vocabulary.html",
        lemmas=rows,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        q=search,
        has_state=has_state,
        languages=languages,
        pos_options=pos_options,
        language_id=language_id,
        pos_id=pos_id,
        status=status,
        sort=sort,
        pagination_query=pagination_query,
    )


@app.route("/admin/vocabulary/bulk-action/", methods=["POST"])
@login_required
@admin_required
def admin_vocabulary_bulk_action():
    """Admin: Apply a bulk action to selected vocabulary lemmas."""
    lemma_columns = table_columns("lemma")
    has_state = "state" in lemma_columns
    has_archived_at = "archived_at" in lemma_columns

    action = (request.form.get("action") or "").strip().lower()
    lemma_ids_raw = request.form.getlist("lemma_ids")

    lemma_ids = []
    for value in lemma_ids_raw:
        try:
            lemma_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    redirect_url = (
        f"/admin/vocabulary/?page={int(request.form.get('page') or 1)}"
        f"&per_page={int(request.form.get('per_page') or 20)}"
        f"&q={(request.form.get('q') or '').strip()}"
    )

    if len(lemma_ids) == 0:
        flash("Select at least one vocabulary row.")
        return redirect(redirect_url)

    if not has_state:
        flash("Bulk state actions are not available on this schema.")
        return redirect(redirect_url)

    if action not in {"publish", "archive"}:
        flash("Choose a valid bulk action.")
        return redirect(redirect_url)

    placeholders = ",".join(["?"] * len(lemma_ids))

    if action == "publish":
        if has_archived_at:
            sql = f"UPDATE lemma SET state = 'published', archived_at = NULL WHERE id IN ({placeholders})"
        else:
            sql = f"UPDATE lemma SET state = 'published' WHERE id IN ({placeholders})"
    else:
        if has_archived_at:
            sql = f"UPDATE lemma SET state = 'archived', archived_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})"
        else:
            sql = f"UPDATE lemma SET state = 'archived' WHERE id IN ({placeholders})"

    result = db.execute(sql, tuple(lemma_ids))
    con.commit()
    flash(f"Updated {result.rowcount} vocabulary rows.")
    return redirect(redirect_url)


@app.route("/admin/vocabulary/edit/<int:lemma_id>/", methods=["GET", "POST"])
@login_required
@admin_required
def admin_vocabulary_edit(lemma_id):
    """Admin: Edit a single canonical vocabulary lemma."""
    lemma_columns = table_columns("lemma")
    has_image = "image_path" in lemma_columns
    has_state = "state" in lemma_columns

    pos_options = db.execute(
        "SELECT id, type FROM word_type ORDER BY type ASC"
    ).fetchall()

    image_select = "l.image_path AS image_path" if has_image else "NULL AS image_path"
    state_select = "l.state AS state" if has_state else "'published' AS state"

    base_select = f"""
        SELECT l.id AS lemma_id,
               l.language_id,
               l.pos_id,
               {image_select},
               {state_select},
               s.id AS sense_id,
               s.gloss AS definition,
               lf.value AS lemma_value,
               COALESCE(ll.charcode, '') AS lang_code,
               COALESCE(ll.name, '') AS language_name,
               (SELECT COUNT(*) FROM set_item si JOIN sense s ON s.id = si.sense_id WHERE s.lemma_id = l.id) AS uses
        FROM lemma l
        JOIN lemma_form lf ON lf.lemma_id = l.id AND lf.is_primary = 1
        JOIN sense s ON s.lemma_id = l.id AND s.is_primary = 1
        LEFT JOIN languages ll ON ll.id = l.language_id
        WHERE l.id = ?
        LIMIT 1
    """

    lemma = db.execute(base_select, (lemma_id,)).fetchone()
    if lemma is None:
        flash("Vocabulary item not found.")
        return redirect("/admin/vocabulary/")

    vocalization_rows = db.execute(
        """
        SELECT id, value, is_primary
        FROM lemma_form
        WHERE lemma_id = ? AND language_id = ?
        ORDER BY is_primary DESC, id ASC
        """,
        (lemma_id, lemma["language_id"]),
    ).fetchall()
    vocalization_row = None
    fallback_vocalization_row = None
    for row in vocalization_rows:
        if int(row["is_primary"] or 0) == 1:
            continue
        if has_nikkud(row["value"]):
            vocalization_row = row
            break
        if fallback_vocalization_row is None:
            fallback_vocalization_row = row
    if vocalization_row is None:
        vocalization_row = fallback_vocalization_row

    state_options = ["draft", "review", "approved", "published", "archived"]

    if request.method == "POST":
        new_value = (request.form.get("lemma_value") or "").strip()
        vocalization = (request.form.get("vocalization") or "").strip()
        definition = (request.form.get("definition") or "").strip()
        new_pos_id = int(request.form.get("pos_id") or lemma["pos_id"])
        image_path = (request.form.get("image_path") or "").strip()
        new_state = (request.form.get("state") or "published").strip()

        if not new_value:
            flash("Lemma value is required.")
            return render_template(
                "admin/vocabulary_edit.html",
                lemma=lemma,
                pos_options=pos_options,
                has_image=has_image,
                vocalization=vocalization,
                definition=definition,
            )

        if has_nikkud(new_value):
            flash("Primary form cannot contain vowel marks (nikkud). Please use the vocalization field for vowelized forms.")
            return render_template(
                "admin/vocabulary_edit.html",
                lemma=lemma,
                pos_options=pos_options,
                state_options=state_options,
                has_image=has_image,
                vocalization=vocalization_row["value"] if vocalization_row is not None else "",
                definition=lemma["definition"] or "",
            )

        db.execute("UPDATE lemma SET pos_id = ?, state = ? WHERE id = ?", (new_pos_id, new_state, lemma_id))

        if has_image:
            db.execute("UPDATE lemma SET image_path = ? WHERE id = ?", (image_path or None, lemma_id))

        # Delete any non-primary forms with the same value as the new primary form to avoid UNIQUE constraint violation
        try:
            db.execute(
                """
                DELETE FROM lemma_form
                WHERE lemma_id = ? AND is_primary = 0 AND value = ?
                """,
                (lemma_id, new_value),
            )

            db.execute(
                """
                UPDATE lemma_form
                SET value = ?, search_key = ?
                WHERE lemma_id = ? AND is_primary = 1
                """,
                (new_value, compute_search_key(new_value, lemma["lang_code"]), lemma_id),
            )
        except sqlite3.IntegrityError as e:
            flash(f"Cannot update primary form: this value already exists. Please choose a different form or delete the conflicting entry.", 400)
            return render_template(
                "admin/vocabulary_edit.html",
                lemma=lemma,
                pos_options=pos_options,
                state_options=state_options,
                has_image=has_image,
                vocalization=vocalization_row["value"] if vocalization_row is not None else "",
                definition=lemma["definition"] or "",
            )

        if vocalization:
            if vocalization_row is not None:
                db.execute(
                    """
                    UPDATE lemma_form
                    SET value = ?, search_key = ?
                    WHERE id = ?
                    """,
                    (vocalization, compute_search_key(vocalization, lemma["lang_code"]), int(vocalization_row["id"])),
                )
            else:
                db.execute(
                    """
                    INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lemma_id,
                        lemma["language_id"],
                        "surface",
                        "Hebr" if (lemma["lang_code"] or "").lower() == "he" else "Latn",
                        vocalization,
                        compute_search_key(vocalization, lemma["lang_code"]),
                        0,
                    ),
                )
        elif vocalization_row is not None and has_nikkud(vocalization_row["value"]):
            db.execute("DELETE FROM lemma_form WHERE id = ?", (int(vocalization_row["id"]),))

        db.execute(
            "UPDATE sense SET gloss = ? WHERE id = ?",
            (definition or None, int(lemma["sense_id"])),
        )

        # Admin helper: link a translation by primary form in the preferred language
        translation_word = (request.form.get("translation_word") or "").strip()
        if translation_word:
            # Prefer English as the admin helper target; fall back to any available 'en' row
            pref_row = db.execute("SELECT id FROM languages WHERE charcode = 'en' LIMIT 1").fetchone()
            if pref_row:
                pref_lang_id = pref_row["id"]
                target_lemma_row = db.execute(
                    """
                    SELECT lf.lemma_id
                    FROM lemma_form lf
                    WHERE lf.language_id = ? AND lf.is_primary = 1 AND LOWER(lf.value) = LOWER(?)
                    LIMIT 1
                    """,
                    (pref_lang_id, translation_word),
                ).fetchone()
                if target_lemma_row is not None:
                    target_lemma_id = int(target_lemma_row["lemma_id"])
                    source_sense_row = db.execute(
                        "SELECT id FROM sense WHERE lemma_id = ? AND is_primary = 1 LIMIT 1",
                        (lemma_id,),
                    ).fetchone()
                    target_sense_row = db.execute(
                        "SELECT id FROM sense WHERE lemma_id = ? AND is_primary = 1 LIMIT 1",
                        (target_lemma_id,),
                    ).fetchone()
                    if source_sense_row and target_sense_row:
                        src_id = int(source_sense_row["id"])
                        tgt_id = int(target_sense_row["id"])
                        exists = db.execute(
                            "SELECT 1 FROM sense_translation WHERE source_sense_id = ? AND target_sense_id = ? LIMIT 1",
                            (src_id, tgt_id),
                        ).fetchone()
                        if not exists:
                            db.execute(
                                "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
                                (src_id, tgt_id, "exact"),
                            )
                        # ensure reciprocal mapping exists
                        rev_exists = db.execute(
                            "SELECT 1 FROM sense_translation WHERE source_sense_id = ? AND target_sense_id = ? LIMIT 1",
                            (tgt_id, src_id),
                        ).fetchone()
                        if not rev_exists:
                            db.execute(
                                "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
                                (tgt_id, src_id, "exact"),
                            )

        con.commit()
        flash("Vocabulary updated.")
        return redirect(f"/admin/vocabulary/edit/{lemma_id}/")

    return render_template(
        "admin/vocabulary_edit.html",
        lemma=lemma,
        pos_options=pos_options,
        state_options=state_options,
        has_image=has_image,
        vocalization=vocalization_row["value"] if vocalization_row is not None else "",
        definition=lemma["definition"] or "",
    )


@app.route("/admin/vocabulary/create/", methods=["GET", "POST"])
@login_required
@admin_required
def admin_vocabulary_create():
    """Admin: Create a new canonical vocabulary lemma."""
    lemma_columns = table_columns("lemma")
    has_image = "image_path" in lemma_columns

    languages = db.execute(
        "SELECT id, name, charcode FROM languages ORDER BY name ASC"
    ).fetchall()
    pos_options = db.execute(
        "SELECT id, type FROM word_type ORDER BY type ASC"
    ).fetchall()
    state_options = ["draft", "review", "approved", "published", "archived"]

    if request.method == "POST":
        lemma_value = (request.form.get("lemma_value") or "").strip()
        vocalization = (request.form.get("vocalization") or "").strip()
        definition = (request.form.get("definition") or "").strip()
        language_id = int(request.form.get("language_id") or 0)
        pos_id = int(request.form.get("pos_id") or 0)
        image_path = (request.form.get("image_path") or "").strip()
        state = (request.form.get("state") or "draft").strip()

        if not lemma_value or not language_id or not pos_id:
            flash("Lemma, language, and part of speech are required.")
            return render_template(
                "admin/vocabulary_create.html",
                languages=languages,
                pos_options=pos_options,
                state_options=state_options,
                has_image=has_image,
                vocalization=vocalization,
                definition=definition,
            )

        language_row = db.execute(
            "SELECT id, charcode FROM languages WHERE id = ? LIMIT 1",
            (language_id,),
        ).fetchone()
        if language_row is None:
            flash("Invalid language.")
            return render_template(
                "admin/vocabulary_create.html",
                languages=languages,
                pos_options=pos_options,
                state_options=state_options,
                has_image=has_image,
                vocalization=vocalization,
                definition=definition,
            )

        lemma_id = db.execute(
            "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
            (language_id, pos_id, "", None),
        ).lastrowid

        if has_image:
            db.execute(
                "UPDATE lemma SET image_path = ? WHERE id = ?",
                (image_path or None, lemma_id),
            )

        lang_code = (language_row["charcode"] or "")
        db.execute(
            """
            INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lemma_id,
                language_id,
                "surface",
                "Hebr" if lang_code.lower() == "he" else "Latn",
                lemma_value,
                compute_search_key(lemma_value, lang_code),
                1,
            ),
        )

        if vocalization:
            db.execute(
                """
                INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lemma_id,
                    language_id,
                    "surface",
                    "Hebr" if lang_code.lower() == "he" else "Latn",
                    vocalization,
                    compute_search_key(vocalization, lang_code),
                    0,
                ),
            )

        db.execute(
            "INSERT INTO sense (lemma_id, part_of_speech, is_primary, gloss) VALUES (?, ?, ?, ?)",
            (lemma_id, pos_id, 1, definition or None),
        )

        db.execute("UPDATE lemma SET state = ? WHERE id = ?", (state, lemma_id))

        con.commit()
        flash("Vocabulary created.")
        return redirect(f"/admin/vocabulary/edit/{lemma_id}/")

    return render_template(
        "admin/vocabulary_create.html",
        languages=languages,
        pos_options=pos_options,
        state_options=state_options,
        has_image=has_image,
        vocalization="",
        definition="",
    )


@app.route("/admin/upload/", methods=["GET", "POST"])
@login_required
@admin_required
def admin_upload():
    """Admin: CSV upload entry point for vocabulary sets."""
    sets = get_sets()
    if request.method == "POST":
        return _handle_uploadwordset_post()
    return render_template("admin/upload.html", sets=sets)


@app.route("/logout", methods=["POST"])
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")


@app.route("/signup", methods=["GET", "POST"])
@limiter.limit("5 per minute", key_func=auth_limit_key)
def signup():
    """Sign up user"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password")
        password2 = request.form.get("confirmation")

        username_error = validate_username(username)
        if username_error:
            return apology(username_error, 400)

        password_error = validate_password_strength(password)
        if password_error:
            return apology(password_error, 400)

        elif not (password == password2):
            return apology("passwords must match", 400)
        elif not password2:
            return apology("must confirm password", 400)
        rows = db.execute("SELECT * FROM users WHERE username = ?", (username, )).fetchall()
        if len(rows) != 1:
            lastrow = (db.execute("INSERT INTO users(username, password, created_at, preferred_lang, learning_lang, roles) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)",
                                 (username, generate_password_hash(password), 1, 2, 1, ))).lastrowid
            con.commit()
            session["user_id"] = lastrow
            session["username"] = username
            set_languages(session["user_id"])
            initialize_user_pet_unlocks(session["user_id"])
            return redirect("/")
        else:
            return apology("username already taken", 400)
    else:
        return render_template("signup.html")


@app.route("/about")
def about():
    """About page"""
    return render_template("about.html")


@app.route("/profile", methods=["GET"])
@login_required
def profile():
    """User Profile"""
    userinfo = get_user_profile(session_get_int("user_id"))

    if userinfo is None:
        return apology("error accessing profile", 400)

    language_options = db.execute("SELECT * FROM languages").fetchall()
    progress = get_learning_progress(session_get_int("user_id"))

    return render_template(
        "profile.html",
        userinfo=userinfo,
        usd=usd,
        language_options=language_options,
        progress=progress,
        joined_display=format_timestamp(userinfo["created_at"]),
    )


@app.route("/users/<identifier>", methods=["GET"])
def public_profile(identifier):
    """Public user profile page."""
    userinfo = get_user_profile(identifier)

    if userinfo is None:
        return apology("user not found", 404)

    user_id = int(userinfo["id"])
    pets_owned = get_user_pets(user_id)
    progress = get_learning_progress(user_id)
    is_self = session_get_int("user_id") == user_id

    return render_template(
        "user_profile.html",
        userinfo=userinfo,
        pets_owned=pets_owned,
        progress=progress,
        joined_display=format_timestamp(userinfo["created_at"]),
        pet_created_display=format_timestamp,
        is_self=is_self,
    )


@app.route("/uploadwordset", methods=["POST"])
@login_required
@admin_required
def uploadFiles():
    """Admin: Allows an admin to upload a CSV to add more words to a word set"""
    return _handle_uploadwordset_post()


def _handle_uploadwordset_post():
    uploaded_file = request.files['file']

    if request.form.get("word_set_id"):
        word_set_id = request.form.get("word_set_id")

        if uploaded_file.filename != '':
            original_filename = uploaded_file.filename
            _, extension = os.path.splitext(original_filename)
            extension = extension.lower()
            safe_root = secure_filename(os.path.splitext(original_filename)[0])
            safe_filename = f"{safe_root}{extension}" if safe_root else f"upload{extension}"
            if not safe_filename or extension not in ALLOWED_UPLOAD_EXTENSIONS:
                return apology("invalid file type", 400)

            # Set the file path and save
            file_path = os.path.join(
                app.config['UPLOAD_FOLDER'], safe_filename)
            uploaded_file.save(file_path)

            additional_set = (request.form.get("additional_set") or "").strip()
            if additional_set and additional_set.isdigit():
                orig_set_id = additional_set
                num_words = save_words(file_path, word_set_id, orig_set_id)
            else:
                num_words = save_words(file_path, word_set_id)
            flash(str(num_words) + " words added to word set")

            # Delete file from static after parsing
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect("/edit/set/?set_id=" + word_set_id)
    return redirect("/")


@app.route("/pets/edit/", methods=["GET", "POST"])
@login_required
def petedit():
    """Allows a user to rename a pet in their account"""
    if request.method == "POST":
        pet_id = request.form.get("pet_id")
        rename = (request.form.get("rename") or "").strip()

        if not PET_NAME_PATTERN.fullmatch(rename):
            return apology("pet name must be 1-50 chars and only letters, numbers, spaces, apostrophes, or hyphens", 400)

        rows = db.execute("SELECT count(*) as count FROM owners WHERE owner_id = ? AND pet_id = ?",
                      (session_get_int("user_id"), pet_id, )).fetchall()
        # Confirmed user owns this pet
        if rows[0]['count'] == 1:
            exp = db.execute("SELECT exp FROM pets WHERE id = ?", (pet_id, )).fetchall()
            total_exp = int(exp[0]['exp'])
            level = get_level_from_exp(total_exp)
            if level >= 2:
                db.execute("UPDATE pets SET name = ? WHERE id = ?", (rename, pet_id, ))
                con.commit()

                # Put updated info into session for pet
                set_active_pet_in_session(session_get_int("user_id"))
                flash("Pet renamed to " + rename)
            else:
                return apology("Your pet needs to reach level 2 to be renamed!", 403)

        return redirect('/pets/edit/?id='+ str(pet_id))
    else:
        pet_id = int(request.args.get('id'))

        # This ensures the current user owns the pet being renamed
        pet_columns = table_columns("pets")
        gender_column = ", pets.gender" if "gender" in pet_columns else ""
        pet_info = db.execute(f"SELECT pets.id, pet_types.imgsrc, pet_types.pet_type, pets.created, pets.exp, pets.name{gender_column}, users.active_pet_id FROM owners JOIN pets ON pets.id = owners.pet_id JOIN pet_types ON pets.type = pet_types.id JOIN users ON users.id = owners.owner_id WHERE owner_id = ? AND pet_id = ?", 
            (session_get_int("user_id"), pet_id, )).fetchall()
        if len(pet_info) == 1:
            pet_info = [
                {
                    **dict(pet),
                    "gender": dict(pet).get("gender") or "neutral",
                    "gender_label": get_pet_gender_label(dict(pet).get("gender")),
                    "gender_icon_class": get_pet_gender_icon_class(dict(pet).get("gender")),
                }
                for pet in pet_info
            ]
            return render_template("petedit.html", pet_info=pet_info)
        else:
            return apology("Error getting pet info", 403)


@app.route("/updatelanguage", methods=["GET", "POST"])
@login_required
def updatelanguage():
    """User Profile - change preference for native and learning language"""
    if request.method == "POST":

        preferred_lang = parse_and_validate_language_id(request.form.get("orig_language"))
        learning_lang = parse_and_validate_language_id(request.form.get("learning_lang"))

        if preferred_lang is None or learning_lang is None:
            return apology("invalid language selection", 400)

        if (preferred_lang == learning_lang):
            return apology("Preferred language and learning language cannot be the same :)", 400)

        db.execute("UPDATE users SET preferred_lang = ? WHERE id = ?",
                   (preferred_lang, session_get_int("user_id"), ))
        con.commit()
        db.execute("UPDATE users SET learning_lang = ? WHERE id = ?",
                   (learning_lang, session_get_int("user_id"), ))
        con.commit()
        set_languages(session_get_int("user_id"))

        return redirect("/profile")
    else:
        return redirect("/profile")


@app.route("/updatepassword", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per 10 minutes", key_func=password_limit_key)
def updatepassword():
    """User Profile - allows a user to change their password"""
    if request.method == "POST":

        current_password = request.form.get("current_password")
        password = request.form.get("password")
        password2 = request.form.get("confirmation")

        if not current_password:
            return apology("must provide current password", 400)

        password_error = validate_password_strength(password)
        if password_error:
            return apology(password_error, 400)

        elif not (password == password2):
            return apology("passwords must match", 400)

        elif not password2:
            return apology("must confirm password", 400)

        rows = db.execute(
            "SELECT password FROM users WHERE id = ?", (session_get_int("user_id"), )).fetchall()

        if not check_password_hash(rows[0]["password"], current_password):
            return apology("current password is incorrect", 403)

        if (check_password_hash(rows[0]["password"], password)):
            return apology("password cannot be the same as existing password", 400)

        else:
            db.execute("UPDATE users SET password = ? WHERE id = ?",
                       (generate_password_hash(password), session_get_int("user_id")))
            con.commit()

        return redirect("/profile")
    else:
        return redirect("/profile")


@app.route("/adopt", methods=["GET", "POST"])
@login_required
def adopt():
    """Allows a user to add a new pet to their account """
    if request.method == "POST":
        user_id = session_get_int("user_id")
        # Check if user bought a pet
        if not request.form.get("pet_type"):
            return apology("must choose pet type", 403)
        try:
            pet_type_id = int(request.form.get("pet_type"))
        except (TypeError, ValueError):
            return apology("invalid pet type", 403)

        if not can_user_adopt_pet_type(user_id, pet_type_id):
            return apology("pet type is locked", 403)

        petname = db.execute(
            "SELECT pet_type, default_gender FROM pet_types WHERE id = ?", (pet_type_id, )).fetchall()
        if len(petname) != 1:
            return apology("invalid pet type", 403)

        pet_gender = choose_pet_gender(petname[0]["default_gender"] if "default_gender" in petname[0].keys() else None)

        # Create pet with default name as pet type
        pet_columns = table_columns("pets")
        if "gender" in pet_columns:
            petid = (db.execute("INSERT INTO pets(type, name, exp, created, gender) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
                               (pet_type_id, petname[0]['pet_type'], 0, pet_gender ))).lastrowid
        else:
            petid = (db.execute("INSERT INTO pets(type, name, exp, created) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                               (pet_type_id, petname[0]['pet_type'], 0 ))).lastrowid
        con.commit()

        # Add owner to pet
        db.execute("INSERT INTO owners(owner_id, pet_id) VALUES (?, ?)",
                   (user_id, petid))
        con.commit()

        # Set as user's active pet
        db.execute("UPDATE users SET active_pet_id = ? WHERE id = ?",
                   (petid, user_id ))
        con.commit()
        set_active_pet_in_session(user_id)
        return redirect("/pets")

    else:
        rows = get_adoptable_pet_types_for_user(session_get_int("user_id"))
        if len(rows) < 1:
            return apology("no pets", 403)
        return render_template("adopt.html", pet_types=rows)


@app.route("/abandon/", methods=["POST"])
@login_required
def abandon():
    """Allows a user to remove a pet from their account"""
    try:
        pet_id = int(request.form.get('id'))
    except (TypeError, ValueError):
        return apology("invalid pet id", 400)
    user_id = session_get_int("user_id")

    active_pet_row = db.execute(
        "SELECT active_pet_id FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    was_active_pet = (
        active_pet_row is not None
        and active_pet_row["active_pet_id"] is not None
        and int(active_pet_row["active_pet_id"]) == pet_id
    )

    # Delete pet from pet owners
    # This ensures the current user owns the pet being abandoned
    rows = db.execute("DELETE FROM owners WHERE owner_id = ? AND pet_id = ?",
                      (user_id, pet_id ))
    con.commit()
    if rows.rowcount == 1:
        db.execute("DELETE FROM pets WHERE id = ?", (pet_id, ))
        con.commit()
    else:
        return apology("Error abandoning pet", 403)

    if was_active_pet:
        replacement_row = db.execute(
            "SELECT pet_id FROM owners WHERE owner_id = ? ORDER BY pet_id ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        if replacement_row is not None:
            db.execute(
                "UPDATE users SET active_pet_id = ? WHERE id = ?",
                (int(replacement_row["pet_id"]), user_id),
            )
            con.commit()
            set_active_pet_in_session(user_id)
        else:
            db.execute("UPDATE users SET active_pet_id = NULL WHERE id = ?", (user_id,))
            con.commit()
            session.pop("active_pet", None)

    return redirect('/pets')


@app.route("/activate/", methods=["POST"])
@login_required
def activate():
    """Allows a user to change their active pet"""
    try:
        pet_id = int(request.form.get('id'))
    except (TypeError, ValueError):
        return apology("invalid pet id", 400)

    owned_pet = db.execute(
        "SELECT 1 FROM owners WHERE owner_id = ? AND pet_id = ?",
        (session_get_int("user_id"), pet_id),
    ).fetchone()
    if owned_pet is None:
        return apology("Error activating pet", 403)

    db.execute("UPDATE users SET active_pet_id = ? WHERE id = ?",
               (pet_id, session_get_int("user_id"), ))
    con.commit()
    set_active_pet_in_session(session_get_int("user_id"))
    return redirect('/pets')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
