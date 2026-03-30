import os
import random
import re

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
from connections import REDIS_URL, get_db_connection, get_redis_client
from helpers import apology, login_required, admin_required, usd, set_active_pet_in_session, set_languages, get_sets, get_set_by_id, get_words_by_set_id, get_role, get_word_translation, update_experience, session_get_int, using_lemma_schema
from fileparser import save_words
from normalization import compute_search_key

r = get_redis_client()

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

LANGUAGES = {
    'en': 'English',
    'he': 'Hebrew'
}
app.config['LANGUAGES'] = LANGUAGES

if __name__ == "__main__":
    app.run(host='0.0.0.0')


def get_locale():
    """Set localization for text keys"""
    if has_request_context() and session.get("language") is not None:
        return session.get('language')['charcode']
    return request.accept_languages.best_match(LANGUAGES.keys()) if has_request_context() else 'en'


babel = Babel(app, locale_selector=get_locale)


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


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
    if len(password) < 12:
        return "password must be at least 12 characters"
    if not re.search(r"[A-Z]", password):
        return "password must include an uppercase letter"
    if not re.search(r"[a-z]", password):
        return "password must include a lowercase letter"
    if not re.search(r"\d", password):
        return "password must include a number"
    if not re.search(r"[^A-Za-z0-9]", password):
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
        return render_template("dashboard.html")
    else:
        return render_template("index.html")


@app.route("/pets")
@login_required
def pets():
    """Lists all of user's pets"""
    
    pets_owned = db.execute("SELECT pets.id, pet_types.imgsrc, pet_types.pet_type, pets.created, pets.exp, pets.name, users.active_pet_id FROM owners JOIN pets ON pets.id = owners.pet_id JOIN pet_types ON pets.type = pet_types.id JOIN users ON users.id = owners.owner_id WHERE owner_id = ?", (session_get_int("user_id"), )).fetchall()
    return render_template("list.html", pets_owned=pets_owned)


@app.route("/train")
@login_required
def train():
    """Lists available word sets to learn and test on"""
    role = get_role()
    sets = get_sets()
    return render_template("train.html", sets=sets, role=role)


@app.route("/train/set/")
@login_required
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
    """Admin: Placeholder word edit route that redirects to the containing set editor."""
    word_id = request.values.get("word_id")
    if not word_id:
        flash("Missing word id")
        return redirect("/edit/set")

    set_row = None
    if using_lemma_schema():
        set_row = db.execute(
            "SELECT word_set_id FROM set_item WHERE sense_id = ? ORDER BY id ASC LIMIT 1",
            (int(word_id),),
        ).fetchone()
    else:
        set_row = db.execute(
            "SELECT word_set_id FROM word_set_words WHERE word_id = ? ORDER BY id ASC LIMIT 1",
            (int(word_id),),
        ).fetchone()

    flash("Word inline editing is not implemented yet; opened the set editor instead.")
    if set_row is not None:
        return redirect(f"/edit/set/?set_id={int(set_row['word_set_id'])}")
    return redirect("/edit/set")


@app.route("/quiz/set/", methods=["GET", "POST"])
@login_required
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

            if using_lemma_schema():
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

                insert_word_set = db.execute(
                    "INSERT INTO word_sets (imgsrc, set_name_word_id, language_id, set_name_sense_id) VALUES (?, ?, ?, ?)",
                    ("/sets/fruits.png", None, learning_lang, learning_sense_id),
                ).lastrowid
                insert_word_set_orig = db.execute(
                    "INSERT INTO word_sets (imgsrc, set_name_word_id, language_id, set_name_sense_id) VALUES (?, ?, ?, ?)",
                    ("/sets/fruits.png", None, preferred_lang, preferred_sense_id),
                ).lastrowid
                con.commit()

            else:
                # Sets will usually be a noun
                learning_wordid = (db.execute("INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (?, ?, ?, ?)",
                                            (learning_lang, 1, '', setname, ))).lastrowid
                con.commit()

                preferred_wordid = (db.execute("INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (?, ?, ?, ?)",
                                            (preferred_lang, 1, '', plang_setname, ))).lastrowid
                con.commit()

                db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)",
                        (preferred_lang, learning_lang, preferred_wordid, learning_wordid, )).fetchall()
                db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)",
                        (learning_lang, preferred_lang, learning_wordid, preferred_wordid, )).fetchall()
                con.commit()

                # TODO Set a default image here
                insert_word_set = (db.execute("INSERT INTO word_sets (imgsrc, set_name_word_id, language_id) VALUES (?, ?, ?)",
                                            ("/sets/fruits.png", learning_wordid, learning_lang, ))).lastrowid
                con.commit()

                insert_word_set_orig = (db.execute("INSERT INTO word_sets (imgsrc, set_name_word_id, language_id) VALUES (?, ?, ?)",
                                                ("/sets/fruits.png", preferred_wordid, preferred_lang, ))).lastrowid
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
                if using_lemma_schema():
                    deleteqry = db.execute(
                        "DELETE FROM set_item WHERE sense_id = ? and word_set_id = ?",
                        (request.form.get("word_id"), request.form.get("word_set_id")),
                    )
                else:
                    # delete word from word_sets
                    deleteqry = db.execute("DELETE FROM word_set_words WHERE word_id = ? and word_set_id = ?",
                                        (request.form.get("word_id"), request.form.get("word_set_id")))
                con.commit()
                if (deleteqry.rowcount > 0):
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


@app.route("/logout")
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
    userinfo = db.execute(
        "SELECT username, id, preferred_lang, learning_lang, created_at, email, full_name FROM users WHERE id = ?", (session_get_int("user_id"), )).fetchall()

    language_options = db.execute("SELECT * FROM languages").fetchall()

    if (len(userinfo) > 0):
        return render_template("profile.html", userinfo=userinfo[0], usd=usd, language_options=language_options)

    return apology("error accessing profile", 400)


@app.route("/uploadwordset", methods=["GET", "POST"])
@login_required
@admin_required
def uploadFiles():
    """Admin: Allows an admin to upload a CSV to add more words to a word set"""
    if request.method == "POST":
        uploaded_file = request.files['file']

        if request.form.get("word_set_id"):
            word_set_id = request.form.get("word_set_id")

            if uploaded_file.filename != '':
                safe_filename = secure_filename(uploaded_file.filename)
                _, extension = os.path.splitext(safe_filename.lower())
                if not safe_filename or extension not in ALLOWED_UPLOAD_EXTENSIONS:
                    return apology("invalid file type", 400)

                # Set the file path and save
                file_path = os.path.join(
                    app.config['UPLOAD_FOLDER'], safe_filename)
                uploaded_file.save(file_path)

                if request.form.get("additional_set"):
                    orig_set_id = request.form.get("additional_set")
                    num_words = save_words(file_path, word_set_id, orig_set_id)
                else:
                    num_words = save_words(file_path, word_set_id)
                flash(str(num_words) + " words added to word set")
                
                # Delete file from static after parsing
                if os.path.exists(file_path):
                    os.remove(file_path)
                return redirect("/edit/set/?set_id=" + word_set_id)
        return redirect("/")
    else:
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
            if (int(exp[0]['exp']) >= 100):
                db.execute("UPDATE pets SET name = ? WHERE id = ?", (rename, pet_id, ))
                con.commit()

                # Put updated info into session for pet
                set_active_pet_in_session(session_get_int("user_id"))
                flash("Pet renamed to " + rename)
            else:
                return apology("Your pet needs at least 100 experience to be renamed!", 403)

        return redirect('/pets/edit/?id='+ str(pet_id))
    else:
        pet_id = int(request.args.get('id'))

        # This ensures the current user owns the pet being renamed
        pet_info = db.execute("SELECT pets.id, pet_types.imgsrc, pet_types.pet_type, pets.created, pets.exp, pets.name, users.active_pet_id FROM owners JOIN pets ON pets.id = owners.pet_id JOIN pet_types ON pets.type = pet_types.id JOIN users ON users.id = owners.owner_id WHERE owner_id = ? AND pet_id = ?", 
                (session_get_int("user_id"), pet_id, )).fetchall()
        if len(pet_info) == 1:
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
        # Check if user bought a pet
        if not request.form.get("pet_type"):
            return apology("must choose pet type", 403)
        pet_type_id = int(request.form.get("pet_type"))
        petname = db.execute(
            "SELECT pet_type FROM pet_types WHERE id = ?", (pet_type_id, )).fetchall()

        # Create pet with default name as pet type
        petid = (db.execute("INSERT INTO pets(type, name, exp, created) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                           (pet_type_id, petname[0]['pet_type'], 0 ))).lastrowid
        con.commit()

        # Add owner to pet
        db.execute("INSERT INTO owners(owner_id, pet_id) VALUES (?, ?)",
                   (session_get_int("user_id"), petid))
        con.commit()

        # Set as user's active pet
        db.execute("UPDATE users SET active_pet_id = ? WHERE id = ?",
                   (petid, session_get_int("user_id") ))
        con.commit()
        set_active_pet_in_session(session_get_int("user_id"))
        return redirect("/pets")

    else:
        rows = db.execute("SELECT * FROM pet_types").fetchall()
        if len(rows) < 1:
            return apology("no pets", 403)
        return render_template("adopt.html", pet_types=rows)


@app.route("/abandon/")
@login_required
def abandon():
    """Allows a user to remove a pet from their account"""
    pet_id = int(request.args.get('id'))

    # TODO
    # Check that active pet is not the one being deleted
    # print("SELECT active_pet_id FROM users WHERE id = ?",
          # session_get_int("user_id"))

    # Delete pet from pet owners
    # This ensures the current user owns the pet being abandoned
    rows = db.execute("DELETE FROM owners WHERE owner_id = ? AND pet_id = ?",
                      (session_get_int("user_id"), pet_id ))
    con.commit()
    if rows.rowcount == 1:
        db.execute("DELETE FROM pets WHERE id = ?", (pet_id, ))
        con.commit()
    else:
        return apology("Error abandoning pet", 403)

    # TODO
    # If active pet is deleted pet, change a different pet to active pet
    # db.execute("UPDATE users SET active_pet_id = ? WHERE id = ?",
    #                              petid, session_get_int("user_id"))
    # set_active_pet_in_session(session_get_int("user_id"))

    return redirect('/pets')


@app.route("/activate/")
@login_required
def activate():
    """Allows a user to change their active pet"""
    pet_id = int(request.args.get('id'))
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
