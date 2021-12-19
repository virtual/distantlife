import os
import random
import redis

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from flask_babel import Babel
from helpers import apology, login_required, admin_required, usd, set_active_pet_in_session, set_languages, get_sets, get_set_by_id, get_words_by_set_id, get_role, get_word_translation, update_experience, session_get_int
from fileparser import save_words

# default it runs on port 6379
r = redis.StrictRedis(host="0.0.0.0", port=6379, db=0)

app = Flask(__name__)
babel = Babel(app)

app.config["TEMPLATES_AUTO_RELOAD"] = True

LANGUAGES = {
    'en': 'English',
    'he': 'Hebrew'
}
app.config['LANGUAGES'] = LANGUAGES

if __name__ == "__main__":
    app.run(host='0.0.0.0')


@babel.localeselector
def get_locale():
    """Set localization for text keys"""
    if (session.get("language") is not None):
        return session.get('language')['charcode']
    return request.accept_languages.best_match(app.config['LANGUAGES'].keys())


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.jinja_env.filters["usd"] = usd
app.config["SESSION_FILE_DIR"] = mkdtemp()

# TODO
# Details on the Secret Key: https://flask.palletsprojects.com/en/1.1.x/config/#SECRET_KEY
# NOTE: The secret key is used to cryptographically-sign the cookies used for storing
#       the session identifiesession.
app.secret_key = 'DL_SESSION_KEY'

# Configure Redis for storing the session data on the server-side
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis.from_url('redis://0.0.0.0:6379')

Session(app)

db = SQL("sqlite:///distantlife.db")


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
    pets_owned = db.execute("SELECT pets.id, pet_types.imgsrc, pet_types.pet_type, pets.created, pets.exp, pets.name, users.active_pet_id FROM owners JOIN pets ON pets.id = owners.pet_id JOIN pet_types ON pets.type = pet_types.id JOIN users ON users.id = owners.owner_id WHERE owner_id = ?", session_get_int("user_id"))
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
            "SELECT id, imgsrc FROM word_sets WHERE id = ?", tset)
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
                    "SELECT id, imgsrc FROM word_sets WHERE id = ?", set_id)

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
            learning_lang = request.form.get('learning_lang')
            plang_setname = request.form.get('plang_setname')
            preferred_lang = request.form.get('preferred_lang')

            # Sets will usually be a noun
            learning_wordid = db.execute("INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (?, ?, ?, ?)",
                                         learning_lang, 1, '', setname)

            preferred_wordid = db.execute("INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (?, ?, ?, ?)",
                                          preferred_lang, 1, '', plang_setname)

            db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)",
                       preferred_lang, learning_lang, preferred_wordid, learning_wordid)
            db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)",
                       learning_lang, preferred_lang, learning_wordid, preferred_wordid)

            # TODO Set a default image here
            insert_word_set = db.execute("INSERT INTO word_sets (imgsrc, set_name_word_id, language_id) VALUES (?, ?, ?)",
                                         "/sets/fruits.png", learning_wordid, learning_lang)
            insert_word_set_orig = db.execute("INSERT INTO word_sets (imgsrc, set_name_word_id, language_id) VALUES (?, ?, ?)",
                                              "/sets/fruits.png", preferred_wordid, preferred_lang)

            if (insert_word_set > 0):
                flash("New set created: " + setname)
            if (insert_word_set_orig > 0):
                flash("New set created: " + plang_setname)

            else:
                flash("Error creating new set")
            sets = get_sets()
        return render_template("editsets.html", sets=sets)
    else:
        language_options = db.execute("SELECT * FROM languages")
        userinfo = db.execute(
            "SELECT username, id, preferred_lang, learning_lang, created_at, email, full_name FROM users WHERE id = ?", session_get_int("user_id"))
        return render_template("createset.html", language_options=language_options, userinfo=userinfo[0])


@app.route("/delete/word_set_word/", methods=["POST"])
@login_required
@admin_required
def delete_word():
    """Admin: Deletes word from word set only"""

    if request.method == "POST":
        if request.form.get('word_id') is not None:
            if request.form.get('word_set_id') is not None:
                # delete word from word_sets
                deleteqry = db.execute("DELETE FROM word_set_words WHERE word_id = ? and word_set_id = ?",
                                       request.form.get("word_id"), request.form.get("word_set_id"))
                if (deleteqry > 0):
                    flash('delete successful')
    return redirect("/edit/set")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        session["user_id"] = int(rows[0]["id"])
        session["username"] = request.form.get("username")

        set_active_pet_in_session(session_get_int("user_id"))
        set_languages(session_get_int("user_id"))
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    r.flushdb()
    return redirect("/")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Sign up user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password2 = request.form.get("confirmation")
        if not username:
            return apology("must provide username", 400)
        elif not password:
            return apology("must provide password", 400)
        elif not (password == password2):
            return apology("passwords must match", 400)
        elif not password2:
            return apology("must confirm password", 400)
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 1:
            lastrow = db.execute("INSERT INTO users(username, password, created_at, preferred_lang, learning_lang, roles) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)",
                                 username, generate_password_hash(password), 1, 2, 1)

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
        "SELECT username, id, preferred_lang, learning_lang, created_at, email, full_name FROM users WHERE id = ?", session_get_int("user_id"))

    language_options = db.execute("SELECT * FROM languages")

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
                # Set the file path and save
                file_path = os.path.join(
                    app.config['UPLOAD_FOLDER'], uploaded_file.filename)
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


@app.route("/updatelanguage", methods=["GET", "POST"])
@login_required
def updatelanguage():
    """User Profile - change preference for native and learning language"""
    if request.method == "POST":

        preferred_lang = request.form.get("orig_language")
        learning_lang = request.form.get("learning_lang")

        if (preferred_lang == learning_lang):
            return apology("Preferred language and learning language cannot be the same :)", 400)

        rows = db.execute(
            "SELECT password FROM users WHERE id = ?", session_get_int("user_id"))

        db.execute("UPDATE users SET preferred_lang = ? WHERE id = ?",
                   preferred_lang, session_get_int("user_id"))
        db.execute("UPDATE users SET learning_lang = ? WHERE id = ?",
                   learning_lang, session_get_int("user_id"))

        set_languages(session_get_int("user_id"))

        return redirect("/profile")
    else:
        return redirect("/profile")


@app.route("/updatepassword", methods=["GET", "POST"])
@login_required
def updatepassword():
    """User Profile - allows a user to change their password"""
    if request.method == "POST":

        password = request.form.get("password")
        password2 = request.form.get("confirmation")

        if not password:
            return apology("must provide password", 400)

        elif not (password == password2):
            return apology("passwords must match", 400)

        elif not password2:
            return apology("must confirm password", 400)

        rows = db.execute(
            "SELECT password FROM users WHERE id = ?", session_get_int("user_id"))

        if (check_password_hash(rows[0]["password"], password)):
            return apology("password cannot be the same as existing password", 400)

        else:
            db.execute("UPDATE users SET password = ? WHERE id = ?",
                       generate_password_hash(password), session_get_int("user_id"))

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
            "SELECT pet_type FROM pet_types WHERE id = ?", pet_type_id)

        # Create pet with default name as pet type
        petid = db.execute("INSERT INTO pets(type, name, exp, created) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                           pet_type_id, petname[0]['pet_type'], 0)

        # Add owner to pet
        db.execute("INSERT INTO owners(owner_id, pet_id) VALUES (?, ?)",
                   session_get_int("user_id"), petid)

        # Set as user's active pet
        db.execute("UPDATE users SET active_pet_id = ? WHERE id = ?",
                   petid, session_get_int("user_id"))
        set_active_pet_in_session(session_get_int("user_id"))
        return redirect("/")

    else:
        rows = db.execute("SELECT * FROM pet_types")
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
                      session_get_int("user_id"), pet_id)
    if rows == 1:
        db.execute("DELETE FROM pets WHERE id = ?", pet_id)
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
               pet_id, session_get_int("user_id"))
    set_active_pet_in_session(session_get_int("user_id"))
    return redirect('/pets')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
