import csv
from connections import get_db_connection, get_redis_client
from normalization import compute_search_key

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


def save_words(csvf, word_set_id, orig_set_id=''):
    """Open the CSV file and read its contents into memory

    Args:
        csvf (file): the file to process
        word_set_id (str): the translated word set to add to
        orig_set_id (str, optional): The original language word set to add to. Defaults to ''.

    Returns:
        len (int): the number of words added
    """
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
        for row in reader:
            i = 0
            word = {}

            while (i < len(row)):
                key = str(headings[i])
                value = row[i]
                word[key] = value
                i += 1
            words.append(word)

    # Get heading names
    lang1 = headings[0]  # Original Language
    lang1p = headings[1]  # Original transliteration
    lang2 = headings[2]  # Translation Language
    lang2p = headings[3]  # Translation transliteration
    wtype = headings[4]  # Type of word (noun, verb)

    orig_lang_row = db.execute(
        "SELECT id, charcode FROM languages WHERE name = ?",
        (lang1,),
    ).fetchone()
    trans_lang_row = db.execute(
        "SELECT id, charcode FROM languages WHERE name = ?",
        (lang2,),
    ).fetchone()

    orig_lang_id = int(orig_lang_row['id'])
    trans_lang_id = int(trans_lang_row['id'])
    orig_lang_code = (orig_lang_row['charcode'] or '').lower()
    trans_lang_code = (trans_lang_row['charcode'] or '').lower()

    for w in words:
        word_type_id = (db.execute(
            "SELECT id FROM word_type WHERE type = ?", (w[wtype], )).fetchall())[0]['id']

        if using_lemma_schema():
            new_orig_lemma_id = db.execute(
                "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
                (orig_lang_id, word_type_id, w[lang1p], None),
            ).lastrowid
            db.execute(
                "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    new_orig_lemma_id,
                    orig_lang_id,
                    'surface',
                    'Hebr' if orig_lang_code == 'he' else 'Latn',
                    w[lang1],
                    compute_search_key(w[lang1], orig_lang_code),
                    1,
                ),
            )
            new_orig_sense_id = db.execute(
                "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
                (new_orig_lemma_id, word_type_id, 1),
            ).lastrowid

            new_trans_lemma_id = db.execute(
                "INSERT INTO lemma (language_id, pos_id, pronunciation, audiopath) VALUES (?, ?, ?, ?)",
                (trans_lang_id, word_type_id, w[lang2p], None),
            ).lastrowid
            db.execute(
                "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    new_trans_lemma_id,
                    trans_lang_id,
                    'surface',
                    'Hebr' if trans_lang_code == 'he' else 'Latn',
                    w[lang2],
                    compute_search_key(w[lang2], trans_lang_code),
                    1,
                ),
            )
            new_trans_sense_id = db.execute(
                "INSERT INTO sense (lemma_id, part_of_speech, is_primary) VALUES (?, ?, ?)",
                (new_trans_lemma_id, word_type_id, 1),
            ).lastrowid

            db.execute(
                "INSERT INTO set_item (word_set_id, sense_id, prompt_mode) VALUES (?, ?, ?)",
                (int(word_set_id), new_trans_sense_id, 'show_all_forms'),
            )
            if (orig_set_id != ''):
                db.execute(
                    "INSERT INTO set_item (word_set_id, sense_id, prompt_mode) VALUES (?, ?, ?)",
                    (int(orig_set_id), new_orig_sense_id, 'show_all_forms'),
                )

            db.execute(
                "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
                (new_orig_sense_id, new_trans_sense_id, 'exact'),
            )
            db.execute(
                "INSERT INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
                (new_trans_sense_id, new_orig_sense_id, 'exact'),
            )
            con.commit()
        else:
            new_orig_word_id = (db.execute("INSERT INTO words ('wordstr', 'language_id', 'type', 'pronunciation') VALUES (?, ?, ?, ?)",
                                        (w[lang1], orig_lang_id, word_type_id, w[lang1p])
                                        )).lastrowid
            con.commit()
            new_translated_word_id = (db.execute("INSERT INTO words ('wordstr', 'language_id', 'type', 'pronunciation') VALUES (?, ?, ?, ?)",
                                                (w[lang2], trans_lang_id, word_type_id,  w[lang2p])
                                                )).lastrowid
            con.commit()
            db.execute("INSERT INTO word_set_words (word_set_id, word_id) VALUES (?, ?)",
                    (word_set_id, new_translated_word_id))
            con.commit()
            # if orig_set_id is set
            if (orig_set_id != ''):
                db.execute("INSERT INTO word_set_words (word_set_id, word_id) VALUES (?, ?)",
                        (int(orig_set_id), new_orig_word_id))
                con.commit()
            # insert orig and its translation equivalent
            db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)",
                    (orig_lang_id, trans_lang_id, new_orig_word_id, new_translated_word_id))
            con.commit()
            # reverse orig & translation
            db.execute("INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (?, ?, ?, ?)",
                    (trans_lang_id, orig_lang_id, new_translated_word_id, new_orig_word_id))
            con.commit()
    file.close()
    return len(words)
