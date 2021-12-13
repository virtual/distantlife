import os
import requests
import urllib.parse
from cs50 import SQL
# import locale

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

def admin_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        roles = db.execute("SELECT roles FROM users WHERE id = ?", session["user_id"])
        if len(roles) != 1 :
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
  language_info = db.execute("SELECT preferred_lang, learning_lang, dir, charcode, localization FROM users JOIN languages ON users.preferred_lang = languages.id WHERE users.id = ?",
                              user_id)
  if (len(language_info) == 1):
    language = {
      "preferred": language_info[0]['preferred_lang'],
      "learning": language_info[0]['learning_lang'],
      "dir": language_info[0]['dir'],
      "charcode": language_info[0]['charcode'],
      "localization": language_info[0]['localization']
    }
    session["language"] = language
    # locale.setlocale(locale.LC_ALL, app_language)
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
    orig_lang = session['language']['preferred']
  if (trans_lang == ''):
    trans_lang = session['language']['learning']

  translation = db.execute("SELECT wordstr FROM words where id = (SELECT word_translation.trans_word FROM words JOIN word_translation ON word_translation.orig_word = words.id WHERE words.id = ? AND word_translation.trans_lang = ? AND word_translation.orig_lang = ?)", 
  word_id, orig_lang, trans_lang)
  
  return translation[0]['wordstr']

def get_sets():
  setsqry = db.execute("SELECT word_sets.id as id, words.wordstr as wordstr, words.id as setnameid, word_sets.imgsrc FROM word_sets JOIN words ON word_sets.set_name_word_id = words.id WHERE word_sets.language_id =  ?", session['language']['learning'])
  sets = []
  for setinfo in setsqry:
    translation = get_word_translation(int(setinfo['setnameid']))
    totalcount = db.execute("select count(*) as count from word_set_words where word_set_id =  ?", setinfo['id'])
    setinfo = {
      "id": setinfo['id'],
      "set_name": setinfo['wordstr'],
      "imgsrc": setinfo['imgsrc'],
      "totalcount": totalcount[0]['count'],
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
  setsqry = db.execute("SELECT word_sets.id as id, words.wordstr as wordstr, words.id as setnameid, word_sets.imgsrc FROM word_sets JOIN words ON word_sets.set_name_word_id = words.id WHERE word_sets.language_id =  ? AND word_sets.id = ?", session['language']['learning'], set_id)
  return setsqry[0]

def get_words_by_set_id(set_id):
  # words = db.execute("SELECT words.id, words.wordstr, words.pronunciation, word_type.type, word_images.imgsrc FROM words JOIN word_set_words ON word_set_words.word_id = words.id JOIN word_type ON words.type = word_type.id JOIN word_images ON words.imgsrc_id = word_images.id where word_set_words.word_set_id = ?", set_id)  

  words = db.execute("SELECT words.id, words.wordstr, words.pronunciation, word_type.type FROM words JOIN word_set_words ON word_set_words.word_id = words.id JOIN word_type ON words.type = word_type.id where word_set_words.word_set_id = ?", set_id)  

  return words


def get_role():
  rolesqry = db.execute("SELECT roles FROM users WHERE id =  ?", session['user_id'])
  role = rolesqry[0]['roles']
  return role


def update_experience(amount):
  activepetqry = db.execute("SELECT active_pet_id FROM users WHERE id =  ?", session['user_id'])
  active_pet_id = int(activepetqry[0]['active_pet_id'])
  expqry = db.execute("SELECT exp FROM pets WHERE id =  ?", active_pet_id)
  exp = int(expqry[0]['exp']) + int(amount)

  updateqry = db.execute("UPDATE pets SET exp = ? WHERE id = ?", exp, active_pet_id)    
  if (updateqry > 0):
    session["active_pet"]["exp"] = exp
    return exp
  else:
    return 0