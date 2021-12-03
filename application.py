import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, usd

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


app.jinja_env.filters["usd"] = usd

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///distantlife.db")


@app.route("/")
@login_required
def index():
    """dashboard page"""

    return render_template("list.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """signup user"""
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
            lastrow = db.execute("INSERT INTO users(username, hash, cash) VALUES (?, ?, ?)",
                                 username, generate_password_hash(password), 10000)

            session["user_id"] = lastrow
            return redirect("/")
        else:
            return apology("username already taken", 400)
    else:
        return render_template("signup.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User Profile"""
    if request.method == "POST":

        password = request.form.get("password")
        password2 = request.form.get("confirmation")

        if not password:
            return apology("must provide password", 400)

        elif not (password == password2):
            return apology("passwords must match", 400)

        elif not password2:
            return apology("must confirm password", 400)

        rows = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])

        if (check_password_hash(rows[0]["hash"], password)):
            return apology("password cannot be the same as existing password", 400)

        else:
            db.execute("UPDATE users SET hash = ? WHERE id = ?",
                       generate_password_hash(password), session["user_id"])

        return redirect("/")

    else:
        rows = db.execute("SELECT username, id, cash FROM users WHERE id = ?", session["user_id"])
        if (len(rows) > 0):
            return render_template("profile.html", userinfo=rows[0], usd=usd)

    return apology("error accessing profile", 400)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
