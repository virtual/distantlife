from flask import flash, redirect, render_template, session
from functools import wraps
from datetime import datetime
from flask_babel import gettext as _
from connections import get_db_connection, get_redis_client
from lexicon import get_primary_form_for_sense, get_sense_translations

con = get_db_connection()
db = con

r = get_redis_client()


def table_exists(table_name):
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def using_lemma_schema():
    return table_exists("lemma") and table_exists("set_item")


def apology(message, code=400):
    """Render message as an apology to user."""
    return render_template("apology.html", message=message, code=code), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session_get_int("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def adopted_pet_required(f):
    """
    Requires user to have an adopted active pet.
    """
    @login_required
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session_get_int("user_id")
        active_pet = session.get("active_pet")
        if isinstance(active_pet, dict) and active_pet.get("id"):
            return f(*args, **kwargs)

        user_row = db.execute(
            "SELECT active_pet_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user_row is not None and user_row["active_pet_id"] is not None:
            refreshed_pet_id = set_active_pet_in_session(user_id)
            if refreshed_pet_id is not None:
                return f(*args, **kwargs)

            # Active pet reference is stale (e.g., deleted pet). Clear it.
            db.execute("UPDATE users SET active_pet_id = NULL WHERE id = ?", (user_id,))
            con.commit()
            session.pop("active_pet", None)

        flash(_("Before training, adopt your first pet!"))
        return redirect("/adopt")
    return decorated_function


def admin_required(f):
    """
    Decorate routes to require admin role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        roles = db.execute(
            "SELECT roles FROM users WHERE id = ?", (session_get_int('user_id'), )).fetchall()
        if len(roles) != 1:
            return apology("invalid user id", 403)
        else:
            if (int(roles[0]['roles']) != 9):
                # Not Admin
                return redirect("/")
        return f(*args, **kwargs)
    return decorated_function


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def set_active_pet_in_session(user_id):
    """
    Query a user for their active pet and set it in the Session

      :param int user_id - user's ID
      :returns: 
      - id of active pet
    """
    active_pet_info = db.execute("SELECT pets.id, name, pet_types.pet_type, exp, pet_types.imgsrc FROM pets JOIN users ON users.active_pet_id = pets.id JOIN pet_types ON pet_types.id = pets.type WHERE users.id = ?",
                                 (user_id, )).fetchall()
    if (len(active_pet_info) == 1):
        active_pet = {
            "name": active_pet_info[0]['name'],
            "type": active_pet_info[0]['pet_type'],
            "exp": active_pet_info[0]['exp'],
            "id": active_pet_info[0]['id'],
            "imgsrc": active_pet_info[0]['imgsrc']
        }
        session["active_pet"] = active_pet
        return active_pet['id']


def set_languages(user_id):
    """
    Query the preferred and targeted learning languages given a user's id and add them to the session for the language key

      :param int user_id - user's ID
    """

    language_info = db.execute("SELECT preferred_lang, learning_lang, dir, charcode, localization FROM users JOIN languages ON users.preferred_lang = languages.id WHERE users.id = ?",
                               (user_id, )).fetchall()
    if (len(language_info) == 1):
        language = {
            "preferred": language_info[0]['preferred_lang'],
            "learning": language_info[0]['learning_lang'],
            "dir": language_info[0]['dir'],
            "charcode": language_info[0]['charcode'],
            "localization": language_info[0]['localization']
        }
        session["language"] = language
        return True


def get_word_translation(word_id, orig_lang='', trans_lang=''):
    """
    Given word_id, returns translated word in original (native) language

      :param int word_id - word ID in translated language
      :param int orig_lang - the language to return the given word in
      :param int trans_lang - the language the word is in
      :returns: 
          - string - word translated into orig_lang
    """

    if (orig_lang == ''):
        orig_lang = session.get('language')['preferred']
    if (trans_lang == ''):
        trans_lang = session.get('language')['learning']

    if using_lemma_schema():
        source_sense_id = int(word_id)
        translated_senses = get_sense_translations(db, source_sense_id, orig_lang)

        # Fallback for legacy IDs during transition.
        if len(translated_senses) == 0:
            mapped = db.execute(
                """
                SELECT s.id AS sense_id
                FROM lemma l
                JOIN sense s ON s.lemma_id = l.id AND s.is_primary = 1
                WHERE l.legacy_word_id = ?
                LIMIT 1
                """,
                (int(word_id),),
            ).fetchone()
            if mapped is not None:
                source_sense_id = int(mapped['sense_id'])
                translated_senses = get_sense_translations(db, source_sense_id, orig_lang)

        if len(translated_senses) == 0:
            return ''

        form = get_primary_form_for_sense(db, int(translated_senses[0]['sense_id']))
        return form['value'] if form is not None else ''

    translation = db.execute("SELECT wordstr FROM words where id = (SELECT word_translation.trans_word FROM words JOIN word_translation ON word_translation.orig_word = words.id WHERE words.id = ? AND word_translation.trans_lang = ? AND word_translation.orig_lang = ?)",
                             (word_id, orig_lang, trans_lang, )).fetchall()
    if len(translation) == 0:
        return ''
    return translation[0]['wordstr']


def get_sets(language_id='', trans_lang=''):
    """
    Returns all word sets for a given language

      :param int language_id - the language to return the given word in
      :param int trans_lang - the language the word is in
      :returns: 
          - list of words
    """
    if (trans_lang == ''):
        trans_lang = session.get('language')['learning']
    if (language_id == ''):
        language_id = session.get('language')['preferred']

    if using_lemma_schema():
        setsqry = db.execute(
            """
            SELECT word_sets.id AS id,
                   word_sets.imgsrc AS imgsrc,
                   word_sets.set_name_sense_id AS setnameid,
                   lf.value AS wordstr
            FROM word_sets
            LEFT JOIN sense s ON s.id = word_sets.set_name_sense_id
            LEFT JOIN lemma_form lf ON lf.lemma_id = s.lemma_id AND lf.is_primary = 1
            WHERE word_sets.language_id = ?
            """,
            (trans_lang,),
        ).fetchall()
    else:
        setsqry = db.execute("SELECT word_sets.id as id, words.wordstr as wordstr, words.id as setnameid, word_sets.imgsrc FROM word_sets JOIN words ON word_sets.set_name_word_id = words.id WHERE word_sets.language_id =  ?", 
                        (trans_lang, )).fetchall()

    sets = []
    for setinfo in setsqry:
        translation = get_word_translation(
            int(setinfo['setnameid']), language_id, trans_lang)

        if using_lemma_schema():
            totalcount = db.execute(
                "select count(*) as count from set_item where word_set_id =  ?",
                (setinfo['id'],),
            ).fetchall()
        else:
            totalcount = db.execute(
                "select count(*) as count from word_set_words where word_set_id =  ?", 
                (setinfo['id'], )).fetchall()

        learnedcount = 0
        if session_get_int('user_id') is not None:
            if using_lemma_schema():
                learnedcount = db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM words_learned wl
                    JOIN sets_learned sl ON sl.id = wl.sets_learned_id
                    WHERE sl.user_id = ? AND sl.wordsets = ?
                    """,
                    (session_get_int('user_id'), setinfo['id']),
                ).fetchone()['count']
            else:
                learnedcount = db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM words_learned wl
                    JOIN sets_learned sl ON sl.id = wl.sets_learned_id
                    WHERE sl.user_id = ? AND sl.wordsets = ?
                    """,
                    (session_get_int('user_id'), setinfo['id']),
                ).fetchone()['count']

        setinfo = {
            "id": setinfo['id'],
            "set_name": setinfo['wordstr'],
            "imgsrc": setinfo['imgsrc'],
            "totalcount": totalcount[0]['count'],
            "completed": int(totalcount[0]['count']) > 0 and int(learnedcount) >= int(totalcount[0]['count']),
            "translation": translation
        }
        sets.append(setinfo)
    return sets


def get_set_by_id(set_id):
    """
      Returns set information for a specific word set 

      :param int set_id: word set ID
      :returns: 
          - id - word set ID
          - wordstr - name of word set
          - setnameid - word ID of wordstr
          - imgsrc - image path for set cover image
    """
    if using_lemma_schema():
        setsqry = db.execute(
            """
            SELECT word_sets.id AS id,
                   lf.value AS wordstr,
                   word_sets.set_name_sense_id AS setnameid,
                   word_sets.imgsrc AS imgsrc
            FROM word_sets
            LEFT JOIN sense s ON s.id = word_sets.set_name_sense_id
            LEFT JOIN lemma_form lf ON lf.lemma_id = s.lemma_id AND lf.is_primary = 1
            WHERE word_sets.language_id = ? AND word_sets.id = ?
            """,
            (session.get('language')['learning'], set_id),
        ).fetchall()
    else:
        setsqry = db.execute("SELECT word_sets.id as id, words.wordstr as wordstr, words.id as setnameid, word_sets.imgsrc FROM word_sets JOIN words ON word_sets.set_name_word_id = words.id WHERE word_sets.language_id =  ? AND word_sets.id = ?", 
                    (session.get('language')['learning'], set_id, )).fetchall()

    return setsqry[0]


def get_words_by_set_id(set_id):
    """
    Returns all words in a single set

      :param int set_id: word set ID
      :returns: 
          - list of words
    """
    if using_lemma_schema():
        words = db.execute(
            """
            SELECT s.id AS id,
                   lf.value AS wordstr,
                   COALESCE(l.pronunciation, '') AS pronunciation,
                   COALESCE(word_type.type, '') AS type,
                   l.audiopath AS audiosrc
            FROM set_item
            JOIN sense s ON s.id = set_item.sense_id
            JOIN lemma l ON l.id = s.lemma_id
            LEFT JOIN lemma_form lf ON lf.lemma_id = l.id AND lf.is_primary = 1
            LEFT JOIN word_type ON word_type.id = s.part_of_speech
            WHERE set_item.word_set_id = ?
            ORDER BY set_item.id ASC
            """,
            (set_id,),
        ).fetchall()
    else:
        words = db.execute("SELECT words.id, words.wordstr, words.pronunciation, word_type.type, words.audiopath AS audiosrc FROM words JOIN word_set_words ON word_set_words.word_id = words.id JOIN word_type ON words.type = word_type.id where word_set_words.word_set_id = ?", 
                    (set_id, )).fetchall()

    words_with_translation = []
    for word in words:
        word_translation = get_word_translation(int(word["id"]))
        word_with_translation = dict(word)
        word_with_translation["translation"] = word_translation
        words_with_translation.append(word_with_translation)

    return words_with_translation


def get_role():
    """
    Returns the role of the active user

      :returns: 
          - integer - role ID
    """
    rolesqry = db.execute(
        "SELECT roles FROM users WHERE id =  ?", (session_get_int('user_id'), )).fetchall()
    role = rolesqry[0]['roles']
    return role


def session_get_int(key):
    """
    Returns the value of a stored session variable converted to integer

      :returns: 
          - integer
    """
    if session.get(key) is not None:
        return int(session.get(key))
    else:
        return None


def table_columns(table_name):
    """Return column names for a table."""
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def current_timestamp():
    """Return a SQLite-friendly timestamp string."""
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def record_set_learned(user_id, set_id, subject='', word_count=0):
    """Create or refresh a learned-set record for the user."""
    columns = table_columns("sets_learned")
    existing = db.execute(
        "SELECT id FROM sets_learned WHERE user_id = ? AND wordsets = ?",
        (user_id, set_id),
    ).fetchone()

    values = {
        "subject": subject,
        "user_id": user_id,
        "wordsets": set_id,
        "started": current_timestamp(),
        "completed": current_timestamp(),
    }

    if existing is None:
        insert_columns = [column for column in ["subject", "user_id", "wordsets", "started", "completed"] if column in columns]
        placeholders = ", ".join(["?"] * len(insert_columns))
        db.execute(
            f"INSERT INTO sets_learned ({', '.join(insert_columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in insert_columns),
        )
        con.commit()
        return db.execute(
            "SELECT id FROM sets_learned WHERE user_id = ? AND wordsets = ?",
            (user_id, set_id),
        ).fetchone()["id"]

    update_columns = [column for column in ["subject", "completed"] if column in columns]
    if update_columns:
        assignments = ", ".join([f"{column} = ?" for column in update_columns])
        db.execute(
            f"UPDATE sets_learned SET {assignments} WHERE id = ?",
            tuple(values[column] for column in update_columns) + (existing["id"],),
        )
        con.commit()
    return existing["id"]


def record_words_learned(user_id, learned_id, word_ids):
    """Create learned-word rows for the given set completion."""
    columns = table_columns("words_learned")
    word_column = "sense_id" if "sense_id" in columns else "word"
    learned_column = "learned" if "learned" in columns else None
    timestamp_columns = [column for column in ["created_at", "updated_at"] if column in columns]

    for word_id in word_ids:
        existing = db.execute(
            f"SELECT id FROM words_learned WHERE user_id = ? AND {word_column} = ?",
            (user_id, word_id),
        ).fetchone()
        if existing is not None:
            continue

        insert_columns = ["user_id", word_column, "sets_learned_id"]
        values = [user_id, word_id, learned_id]
        if learned_column is not None:
            insert_columns.append(learned_column)
            values.append(True)
        for column in timestamp_columns:
            insert_columns.append(column)
            values.append(current_timestamp())

        placeholders = ", ".join(["?"] * len(insert_columns))
        db.execute(
            f"INSERT INTO words_learned ({', '.join(insert_columns)}) VALUES ({placeholders})",
            tuple(values),
        )

    con.commit()


def get_learning_progress(user_id):
    """Return aggregate learning progress for a user."""
    learned_words = db.execute(
        "SELECT COUNT(*) AS count FROM words_learned WHERE user_id = ?",
        (user_id,),
    ).fetchone()["count"]
    learned_sets = db.execute(
        "SELECT COUNT(*) AS count FROM sets_learned WHERE user_id = ?",
        (user_id,),
    ).fetchone()["count"]
    recent_sets = db.execute(
        """
        SELECT subject, wordsets, completed
        FROM sets_learned
        WHERE user_id = ?
        ORDER BY completed DESC, id DESC
        LIMIT 5
        """,
        (user_id,),
    ).fetchall()
    return {
        "learned_words": learned_words,
        "learned_sets": learned_sets,
        "recent_sets": recent_sets,
    }


def update_experience(amount):
    """
    Updates the experience by the given amount

      :param int amount: experience amount to increase or decrease
      :returns: 
          - int - a pet's total experience including the added amount
    """
    activepetqry = db.execute(
        "SELECT active_pet_id FROM users WHERE id =  ?", (session_get_int('user_id'), )).fetchone()
    active_pet_id = int(activepetqry['active_pet_id'])
    expqry = db.execute("SELECT exp FROM pets WHERE id =  ?", (active_pet_id, )).fetchall()
    exp = int(expqry[0]['exp']) + int(amount)

    updateqry = db.execute(
        "UPDATE pets SET exp = ? WHERE id = ?", (exp, active_pet_id))
    con.commit()
    if (updateqry.rowcount > 0):
        session.get("active_pet")["exp"] = exp
        return exp
    else:
        return 0
