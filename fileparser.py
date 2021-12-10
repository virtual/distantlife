from cs50 import SQL
import csv

db = SQL("sqlite:///distantlife.db")

# Open the CSV file and read its contents into memory
def save_words(csvf):
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

  print("INSERT INTO word_sets (imgsrc, set_name, language_id) VALUES ('/sets/fruits.png', 'fruit', ?)", orig_lang_id)
  print("INSERT INTO word_sets (imgsrc, set_name, language_id) VALUES ('/sets/fruits.png', 'פרי', ?)", trans_lang_id)

  for w in words:
      word_type_id = db.execute("SELECT id FROM word_type WHERE type = ?", w[wtype])[0]['id']

      print("INSERT INTO words ('wordstr', 'language_id', 'type', 'pronunciation') VALUES (?, ?, ?, ?)",
        w[lang1], orig_lang_id, word_type_id, w[lang1p]
      )
      print("INSERT INTO words ('wordstr', 'language_id', 'type', 'pronunciation') VALUES (?, ?, ?, ?)",
        w[lang2], trans_lang_id, word_type_id,  w[lang2p]
      )

      print("INSERT INTO word_set_words (word_set_id, word_id) VALUES (1, 1)")
      
      # insert orig and its translation equivalent
      print("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, 5, 1)", orig_lang_id, trans_lang_id)

      # reverse orig & translation
      # is this really needed?
      print("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (2, 1, 1, 5)")

  file.close()