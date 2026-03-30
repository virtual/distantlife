from normalization import compute_search_key


def _query_all(db, sql, params=()):
    return db.execute(sql, params).fetchall()


def _query_one(db, sql, params=()):
    return db.execute(sql, params).fetchone()


def get_primary_form_for_sense(db, sense_id):
    """Return the primary form for a sense, or fallback to any form."""
    row = _query_one(
        db,
        """
        SELECT lf.value, lf.search_key, lf.script, lf.form_type, lf.language_id
        FROM sense s
        JOIN lemma_form lf ON lf.lemma_id = s.lemma_id
        WHERE s.id = ?
        ORDER BY lf.is_primary DESC, lf.id ASC
        LIMIT 1
        """,
        (sense_id,),
    )
    return row


def get_sense_forms(db, sense_id):
    """Return all forms for the lemma connected to a sense."""
    return _query_all(
        db,
        """
        SELECT lf.id, lf.value, lf.search_key, lf.script, lf.form_type, lf.is_primary, lf.language_id
        FROM sense s
        JOIN lemma_form lf ON lf.lemma_id = s.lemma_id
        WHERE s.id = ?
        ORDER BY lf.is_primary DESC, lf.id ASC
        """,
        (sense_id,),
    )


def get_sense_translations(db, source_sense_id, target_language_id=None):
    """Return translated senses for a source sense, optionally filtered by language."""
    params = [source_sense_id]
    language_filter = ""
    if target_language_id is not None:
        language_filter = " AND l.language_id = ?"
        params.append(target_language_id)

    return _query_all(
        db,
        f"""
        SELECT
            st.target_sense_id AS sense_id,
            s.lemma_id,
            s.gloss,
            s.part_of_speech,
            l.language_id,
            st.relation_type
        FROM sense_translation st
        JOIN sense s ON s.id = st.target_sense_id
        JOIN lemma l ON l.id = s.lemma_id
        WHERE st.source_sense_id = ?{language_filter}
        ORDER BY st.id ASC
        """,
        tuple(params),
    )


def get_set_senses(db, word_set_id):
    """Return the senses assigned to a set with primary display form."""
    return _query_all(
        db,
        """
        SELECT
            si.sense_id,
            s.lemma_id,
            s.gloss,
            s.part_of_speech,
            l.language_id,
            l.pronunciation,
            lf.value AS wordstr,
            lf.search_key,
            lf.script
        FROM set_item si
        JOIN sense s ON s.id = si.sense_id
        JOIN lemma l ON l.id = s.lemma_id
        JOIN lemma_form lf ON lf.lemma_id = l.id
        WHERE si.word_set_id = ?
          AND lf.is_primary = 1
        ORDER BY si.id ASC
        """,
        (word_set_id,),
    )


def search_senses(db, text, language_id=None, limit=20):
    """Search senses by normalized form key."""
    if limit < 1:
        limit = 1

    lang_code = ""
    if language_id is not None:
        lang = _query_one(db, "SELECT charcode FROM languages WHERE id = ?", (language_id,))
        if lang:
            lang_code = lang["charcode"]

    key = compute_search_key(text, lang_code)
    params = [f"%{key}%"]

    language_filter = ""
    if language_id is not None:
        language_filter = " AND l.language_id = ?"
        params.append(language_id)

    params.append(limit)

    return _query_all(
        db,
        f"""
        SELECT
            s.id AS sense_id,
            s.lemma_id,
            s.gloss,
            l.language_id,
            lf.value AS primary_form,
            lf.search_key
        FROM sense s
        JOIN lemma l ON l.id = s.lemma_id
        JOIN lemma_form lf ON lf.lemma_id = l.id AND lf.is_primary = 1
        WHERE lf.search_key LIKE ?{language_filter}
        ORDER BY lf.search_key ASC
        LIMIT ?
        """,
        tuple(params),
    )
