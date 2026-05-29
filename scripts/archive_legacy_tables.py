#!/usr/bin/env python3
"""Archive legacy vocabulary tables.

This script backs up legacy tables to CSV files under `backups/`
and renames the tables in-place to mark them archived (appends a timestamp).

Usage: python scripts/archive_legacy_tables.py --db distantlife.db --backup-dir ./backups --dry-run
"""
import argparse
import csv
import os
import sqlite3
from datetime import datetime
import re


LEGACY_TABLES = [
    "words",
    "word_translation",
    "word_set_words",
    "words_old",
    "word_translation_old",
    "word_set_words_old",
]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def validate_table_name(name):
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Invalid table name: {name}")
    return name


def table_exists(db, name):
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def backup_table(db, name, backup_dir, ts):
    safe_name = validate_table_name(name)
    cursor = db.execute(f"SELECT * FROM {quote_identifier(safe_name)}")
    rows = cursor.fetchall()
    if not rows:
        print(f"[INFO] Table '{name}' exists but is empty; creating empty backup CSV.")
    cols = [description[0] for description in cursor.description]
    os.makedirs(backup_dir, exist_ok=True)
    fname = os.path.join(backup_dir, f"legacy_{name}_{ts}.csv")
    with open(fname, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r[c] for c in cols])
    print(f"[BACKUP] Wrote {len(rows)} rows from '{name}' to {fname}")
    return fname


def rename_table(db, name, ts):
    safe_name = validate_table_name(name)
    new_name = f"{safe_name}_archived_{ts}"
    validate_table_name(new_name)
    sql = f"ALTER TABLE {quote_identifier(safe_name)} RENAME TO {quote_identifier(new_name)}"
    db.execute(sql)
    print(f"[RENAME] {name} -> {new_name}")
    return new_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="distantlife.db", help="Path to SQLite DB")
    parser.add_argument("--backup-dir", default="backups", help="Directory for CSV backups")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be done")
    args = parser.parse_args()

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    db = con

    actions = []
    for t in LEGACY_TABLES:
        if table_exists(db, t):
            actions.append(t)

    if not actions:
        print("No legacy tables found. Nothing to archive.")
        return

    print(f"Found {len(actions)} legacy table(s) to archive: {actions}")
    if args.dry_run:
        print("Dry run; exiting without performing changes.")
        return

    for t in actions:
        try:
            backup_table(db, t, args.backup_dir, ts)
            rename_table(db, t, ts)
            con.commit()
        except Exception as exc:
            print(f"[ERROR] Failed to archive {t}: {exc}")
            con.rollback()

    con.close()
    print("Archival completed.")


if __name__ == "__main__":
    main()
