import argparse
import sqlite3
import sys

REPORT_QUERIES = {
    "row_counts": """
        SELECT (SELECT COUNT(*) FROM words_old) AS old_words,
               (SELECT COUNT(*) FROM lemma) AS lemma_count,
               (SELECT COUNT(*) FROM sense WHERE is_primary = 1) AS primary_sense_count
    """,
    "translation_counts": """
        SELECT (SELECT COUNT(*) FROM word_translation_old) AS old_translation_rows,
               (SELECT COUNT(*) FROM sense_translation) AS sense_translation_rows
    """,
    "set_counts": """
        SELECT (SELECT COUNT(*) FROM word_set_words_old) AS old_set_rows,
               (SELECT COUNT(*) FROM set_item) AS set_item_rows
    """,
    "orphan_lemma_forms": """
        SELECT COUNT(*) AS orphan_lemma_forms
        FROM lemma_form lf
        LEFT JOIN lemma l ON l.id = lf.lemma_id
        WHERE l.id IS NULL
    """,
    "orphan_senses": """
        SELECT COUNT(*) AS orphan_senses
        FROM sense s
        LEFT JOIN lemma l ON l.id = s.lemma_id
        WHERE l.id IS NULL
    """,
    "orphan_set_items": """
        SELECT COUNT(*) AS orphan_set_items
        FROM set_item si
        LEFT JOIN sense s ON s.id = si.sense_id
        WHERE s.id IS NULL
    """,
    "words_learned_without_sense": """
        SELECT COUNT(*) AS words_learned_without_sense
        FROM words_learned
        WHERE word IS NOT NULL AND sense_id IS NULL
    """,
    "duplicate_primary_search_keys": """
        SELECT lf.language_id, lf.search_key, COUNT(*) AS duplicate_count
        FROM lemma_form lf
        WHERE lf.is_primary = 1
        GROUP BY lf.language_id, lf.search_key
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, lf.search_key ASC
        LIMIT 20
    """,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run post-cutover validation checks for lemma/sense schema."
    )
    parser.add_argument(
        "--db",
        default="distantlife.db",
        help="Path to SQLite database (default: distantlife.db)",
    )
    return parser.parse_args()


def run_query(db, name, sql):
    rows = db.execute(sql).fetchall()
    print(f"\n[{name}]")
    if not rows:
        print("(no rows)")
        return rows

    columns = rows[0].keys()
    print(" | ".join(columns))
    for row in rows:
        print(" | ".join(str(row[col]) for col in columns))
    return rows


def main():
    args = parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    db = con

    has_errors = False

    for name, sql in REPORT_QUERIES.items():
        try:
            rows = run_query(db, name, sql)
        except sqlite3.OperationalError as exc:
            print(f"\n[{name}] ERROR: {exc}")
            has_errors = True
            continue

        if name in {
            "orphan_lemma_forms",
            "orphan_senses",
            "orphan_set_items",
            "words_learned_without_sense",
        } and rows and int(rows[0][0]) > 0:
            has_errors = True

    con.close()
    if has_errors:
        print("\nValidation completed with warnings/errors.")
        sys.exit(1)

    print("\nValidation completed successfully.")


if __name__ == "__main__":
    main()
