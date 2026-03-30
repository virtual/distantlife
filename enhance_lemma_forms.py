import argparse
import sqlite3

from normalization import compute_search_key, has_nikkud, strip_nikkud


def get_hebrew_language_ids(db):
    rows = db.execute(
        "SELECT id FROM languages WHERE lower(charcode) = 'he' OR lower(name) = 'hebrew' OR name = 'עברית'"
    ).fetchall()
    return {int(row["id"]) for row in rows}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Enhance lemma forms by adding plain Hebrew variants for niqqud forms."
    )
    parser.add_argument(
        "--db",
        default="distantlife.db",
        help="Path to the SQLite database file (default: distantlife.db)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    db = con

    hebrew_language_ids = get_hebrew_language_ids(db)
    if not hebrew_language_ids:
        print("No Hebrew language id found; skipping form enhancement.")
        return

    placeholders = ",".join(["?"] * len(hebrew_language_ids))
    primary_forms = db.execute(
        f"""
        SELECT lf.id, lf.lemma_id, lf.value, lf.language_id
                         , lf.search_key
        FROM lemma_form lf
        WHERE lf.is_primary = 1
          AND lf.language_id IN ({placeholders})
        """,
        tuple(hebrew_language_ids),
    ).fetchall()

    inserted_plain_forms = 0
    updated_search_keys = 0

    for form in primary_forms:
        value = form["value"] or ""
        language_id = int(form["language_id"])
        search_key = compute_search_key(value, "he")

        if (form["search_key"] or "") != search_key:
            db.execute(
                "UPDATE lemma_form SET search_key = ? WHERE id = ?",
                (search_key, int(form["id"])),
            )
            updated_search_keys += 1

        if not has_nikkud(value):
            continue

        plain_value = strip_nikkud(value)
        existing = db.execute(
            """
            SELECT 1
            FROM lemma_form
            WHERE lemma_id = ? AND language_id = ? AND value = ?
            LIMIT 1
            """,
            (int(form["lemma_id"]), language_id, plain_value),
        ).fetchone()

        if existing:
            continue

        db.execute(
            """
            INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary)
            VALUES (?, ?, 'surface', 'Hebr', ?, ?, 0)
            """,
            (
                int(form["lemma_id"]),
                language_id,
                plain_value,
                compute_search_key(plain_value, "he"),
            ),
        )
        inserted_plain_forms += 1

    con.commit()
    print(f"Updated search_key on primary forms: {updated_search_keys}")
    print(f"Inserted plain Hebrew forms: {inserted_plain_forms}")


if __name__ == "__main__":
    main()
