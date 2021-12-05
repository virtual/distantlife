import os
import requests
import urllib.parse
from cs50 import SQL

from flask import redirect, render_template, request, session
from functools import wraps
db = SQL("sqlite:///distantlife.db")

def apology(message, code=400):
    """Render message as an apology to user."""
    return render_template("apology.html", message=message, code=code)


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def set_active_pet_in_session(user_id):
  # set as user's active pet
  active_pet_info = db.execute("SELECT pets.id, name, pet_types.pet_type, exp, pet_types.imgsrc FROM pets JOIN users ON users.active_pet_id = pets.id JOIN pet_types ON pet_types.id = pets.type WHERE users.id = ?",
                              user_id)
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
  # set as user's active pet
  language_info = db.execute("SELECT preferred_lang, learning_lang, dir, charcode FROM users JOIN languages ON users.preferred_lang = languages.id WHERE users.id = ?",
                              user_id)
  if (len(language_info) == 1):
    language = {
      "preferred": language_info[0]['preferred_lang'],
      "learning": language_info[0]['learning_lang'],
      "dir": language_info[0]['dir'],
      "charcode": language_info[0]['charcode']
    }
    session["language"] = language
    return True