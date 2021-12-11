from cs50 import SQL
import csv

db = SQL("sqlite:///distantlife.db")



# Open the CSV file and read its contents into memory
def save_words(csvf, word_set_id):
  words = []
  headings = []

  with open(csvf, "r", encoding='utf-8-sig') as file:
      reader = csv.reader(file, delimiter=',')

      # Create dictionary keys
      for row in reader:
          i = 0
          while (i < len(row)):
              headings.append(row[i])
              i += 1
          break

      # Save STR values to each person
      # lost in space
      for row in reader:
          i = 0
          word = {}

          while (i < len(row)):
              key = str(headings[i])
              value = row[i]
              # print(value)
              word[key] = value
              i += 1
          words.append(word)

  # Get heading names
  lang1   = headings[0] # Original Language
  lang1p  = headings[1] # Original transliteration
  lang2   = headings[2] # Translation Language
  lang2p  = headings[3] # Translation transliteration
  wtype   = headings[4] # Type of word (noun, verb)

  orig_lang_id = db.execute("SELECT id FROM languages WHERE name = ?", lang1)[0]['id']
  trans_lang_id = db.execute("SELECT id FROM languages WHERE name = ?", lang2)[0]['id']

  # Only if word_set_id is not set?
  # print("INSERT INTO word_sets (imgsrc, set_name, language_id) VALUES ('/sets/fruits.png', 'fruit', ?)", orig_lang_id)
  # print("INSERT INTO word_sets (imgsrc, set_name, language_id) VALUES ('/sets/fruits.png', 'פרי', ?)", trans_lang_id)

  for w in words:
      word_type_id = db.execute("SELECT id FROM word_type WHERE type = ?", w[wtype])[0]['id']

      new_orig_word_id = db.execute("INSERT INTO words ('wordstr', 'language_id', 'type', 'pronunciation') VALUES (?, ?, ?, ?)",
        w[lang1], orig_lang_id, word_type_id, w[lang1p]
      )
      new_translated_word_id = db.execute("INSERT INTO words ('wordstr', 'language_id', 'type', 'pronunciation') VALUES (?, ?, ?, ?)",
        w[lang2], trans_lang_id, word_type_id,  w[lang2p]
      )

      db.execute("INSERT INTO word_set_words (word_set_id, word_id) VALUES (?, ?)", 
            word_set_id, new_translated_word_id)
      
      # insert orig and its translation equivalent
      db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)", 
            orig_lang_id, trans_lang_id, new_orig_word_id, new_translated_word_id)

      # reverse orig & translation
      # is this really needed?
      db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)", 
            trans_lang_id, orig_lang_id, new_translated_word_id, new_orig_word_id)

  file.close()
  return len(words)