#!/usr/bin/env python3
"""Prepare and apply Hebrew-first vocabulary imports.

Workflow:
- `prepare`: build a review CSV from a wordfreq-ranked Hebrew list.
- `apply`: import a reviewed bilingual CSV/JSON file into the canonical lemma schema.

The importer keeps Hebrew as the anchor language:
- primary Hebrew forms are stored without niqqud
- vocalized Hebrew forms are stored as non-primary lemma_form rows
- English translations are stored as translated senses linked via sense_translation
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from connections import get_db_connection
from normalization import compute_search_key, has_nikkud, normalize_lemma_form_value, strip_nikkud


DEFAULT_LANGUAGE_CODE = "he"
DEFAULT_POS = "noun"
DEFAULT_RELATION_TYPE = "exact"
DEFAULT_PREPARE_FIELDS = [
    "rank",
    "hebrew_primary",
    "hebrew_vocalized",
    "english",
    "pos",
    "relation_type",
    "source",
    "confidence",
    "review_status",
    "notes",
]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

CSV_ALIASES = {
    "hebrew_primary": {"hebrew_primary", "hebrew", "lemma", "primary", "source"},
    "hebrew_vocalized": {"hebrew_vocalized", "vocalized", "niqqud", "nikud", "pronunciation"},
    "english": {"english", "translation", "gloss", "target", "en"},
    "pos": {"pos", "part_of_speech", "word_type", "type"},
    "relation_type": {"relation_type", "relation", "translation_relation"},
    "source": {"source", "translation_source", "origin"},
    "confidence": {"confidence", "score", "review_confidence"},
    "review_status": {"review_status", "state", "status"},
    "notes": {"notes", "comment", "remarks"},
    "rank": {"rank", "frequency_rank"},
}


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    if not isinstance(table_name, str) or not _IDENTIFIER_RE.fullmatch(table_name):
        return False
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(db: sqlite3.Connection, table_name: str) -> List[str]:
    if not _table_exists(db, table_name):
        return []
    rows = db.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    return [row["name"] for row in rows]


def _normalize_hebrew_primary(value: Any) -> str:
    text = strip_nikkud(_normalize_text(value))
    return text.strip()


def _language_id(db: sqlite3.Connection, code_or_name: str) -> Optional[int]:
    key = _normalize_text(code_or_name).lower()
    if not key:
        return None

    row = db.execute(
        "SELECT id FROM languages WHERE lower(charcode) = ? OR lower(name) = ? LIMIT 1",
        (key, key),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    return None


def _language_row(db: sqlite3.Connection, code_or_name: str):
    key = _normalize_text(code_or_name).lower()
    if not key:
        return None
    return db.execute(
        "SELECT id, charcode, name FROM languages WHERE lower(charcode) = ? OR lower(name) = ? LIMIT 1",
        (key, key),
    ).fetchone()


def _ensure_word_type_id(db: sqlite3.Connection, pos_name: str) -> int:
    value = _normalize_text(pos_name) or DEFAULT_POS
    row = db.execute("SELECT id FROM word_type WHERE lower(type) = lower(?) LIMIT 1", (value,)).fetchone()
    if row is not None:
        return int(row["id"])

    inserted = db.execute("INSERT INTO word_type (type) VALUES (?)", (value,))
    return int(inserted.lastrowid)


def _script_for_language_code(lang_code: str) -> str:
    return "Hebr" if (lang_code or "").lower() in {"he", "heb", "hebrew"} else "Latn"


def _load_rows_from_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        rows: List[Dict[str, Any]] = []
        for raw_row in reader:
            row: Dict[str, Any] = {}
            normalized = {_normalize_header(key): value for key, value in raw_row.items() if key is not None}
            for canonical, aliases in CSV_ALIASES.items():
                value = ""
                for alias in aliases:
                    if alias in normalized and normalized[alias] not in (None, ""):
                        value = normalized[alias]
                        break
                row[canonical] = value
            rows.append(row)
    return rows


def _load_rows_from_json(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            payload = payload["rows"]
        elif isinstance(payload.get("items"), list):
            payload = payload["items"]
    if not isinstance(payload, list):
        raise ValueError("JSON import file must contain a list of rows or an object with rows/items")

    rows: List[Dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        row: Dict[str, Any] = {}
        normalized = {_normalize_header(key): value for key, value in item.items()}
        for canonical, aliases in CSV_ALIASES.items():
            value = ""
            for alias in aliases:
                if alias in normalized and normalized[alias] not in (None, ""):
                    value = normalized[alias]
                    break
            row[canonical] = value
        rows.append(row)
    return rows


def load_rows(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_rows_from_csv(path)
    if suffix == ".json":
        return _load_rows_from_json(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


def _load_wordfreq_candidates(language_code: str, limit: int) -> List[Tuple[int, str, float]]:
    try:
        from wordfreq import top_n_list, zipf_frequency
    except ImportError as exc:
        raise RuntimeError("wordfreq is required for prepare mode") from exc

    candidates = top_n_list(language_code, limit)
    output: List[Tuple[int, str, float]] = []
    for rank, word in enumerate(candidates, start=1):
        output.append((rank, word, float(zipf_frequency(word, language_code))))
    return output


def _load_translation_index(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if path is None:
        return {}

    rows = load_rows(path)
    indexed: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        primary = _normalize_hebrew_primary(row.get("hebrew_primary") or row.get("hebrew"))
        if not primary:
            continue

        confidence = row.get("confidence") or ""
        existing = indexed.get(primary)
        if existing is None:
            indexed[primary] = row
            continue

        existing_conf = _normalize_text(existing.get("confidence"))
        if _normalize_text(confidence) and not existing_conf:
            indexed[primary] = row

    return indexed


def prepare_rows(limit: int, language_code: str, translations_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    translation_index = _load_translation_index(translations_file)
    rows: List[Dict[str, Any]] = []

    for rank, hebrew, zipf in _load_wordfreq_candidates(language_code, limit):
        primary = _normalize_hebrew_primary(hebrew)
        merged = translation_index.get(primary, {})
        vocalized = _normalize_text(merged.get("hebrew_vocalized"))
        english = normalize_lemma_form_value(_normalize_text(merged.get("english")), "en")
        pos = _normalize_text(merged.get("pos")) or ""
        relation_type = _normalize_text(merged.get("relation_type")) or DEFAULT_RELATION_TYPE
        source = _normalize_text(merged.get("source")) or "wordfreq"
        confidence = _normalize_text(merged.get("confidence"))
        review_status = _normalize_text(merged.get("review_status")) or ("reviewed" if english else "needs_translation")
        notes = _normalize_text(merged.get("notes"))

        if not vocalized and has_nikkud(hebrew):
            vocalized = _normalize_text(hebrew)

        rows.append(
            {
                "rank": rank,
                "hebrew_primary": primary,
                "hebrew_vocalized": vocalized,
                "english": english,
                "pos": pos,
                "relation_type": relation_type,
                "source": source,
                "confidence": confidence or f"{zipf:.2f}",
                "review_status": review_status,
                "notes": notes,
            }
        )

    return rows


def write_rows_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=DEFAULT_PREPARE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in DEFAULT_PREPARE_FIELDS})


def _find_existing_lemma_id(db: sqlite3.Connection, language_id: int, lang_code: str, primary_value: str) -> Optional[int]:
    search_key = compute_search_key(primary_value, lang_code)
    row = db.execute(
        """
        SELECT l.id
        FROM lemma l
        JOIN lemma_form lf ON lf.lemma_id = l.id
        WHERE lf.language_id = ? AND lf.is_primary = 1 AND lf.search_key = ?
        ORDER BY lf.id ASC
        LIMIT 1
        """,
        (language_id, search_key),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    return None


def _insert_lemma(db: sqlite3.Connection, language_id: int, pos_id: int, pronunciation: str = "") -> int:
    columns = set(_table_columns(db, "lemma"))
    insert_columns = ["language_id", "pos_id"]
    values: List[Any] = [language_id, pos_id]

    if "pronunciation" in columns:
        insert_columns.append("pronunciation")
        values.append(pronunciation or None)
    if "audiopath" in columns:
        insert_columns.append("audiopath")
        values.append(None)
    if "image_path" in columns:
        insert_columns.append("image_path")
        values.append(None)
    if "state" in columns:
        insert_columns.append("state")
        values.append("draft")

    placeholders = ", ".join(["?"] * len(values))
    sql = f"INSERT INTO lemma ({', '.join(insert_columns)}) VALUES ({placeholders})"
    inserted = db.execute(sql, tuple(values))
    return int(inserted.lastrowid)


def _ensure_lemma(
    db: sqlite3.Connection,
    language_id: int,
    pos_id: int,
    primary_value: str,
    lang_code: str,
    pronunciation: str = "",
) -> Tuple[int, bool]:
    existing_id = _find_existing_lemma_id(db, language_id, lang_code, primary_value)
    if existing_id is not None:
        row = db.execute("SELECT pos_id FROM lemma WHERE id = ? LIMIT 1", (existing_id,)).fetchone()
        if row is not None and row["pos_id"] in (None, "", 0):
            db.execute("UPDATE lemma SET pos_id = ? WHERE id = ?", (pos_id, existing_id))
        return existing_id, False

    lemma_id = _insert_lemma(db, language_id, pos_id, pronunciation=pronunciation)
    return lemma_id, True


def _upsert_form(
    db: sqlite3.Connection,
    lemma_id: int,
    language_id: int,
    value: str,
    is_primary: int,
    lang_code: str,
) -> Optional[int]:
    value = _normalize_text(value)
    if not value:
        return None

    search_key = compute_search_key(value, lang_code)
    script = _script_for_language_code(lang_code)
    existing = db.execute(
        "SELECT id, is_primary FROM lemma_form WHERE lemma_id = ? AND value = ? LIMIT 1",
        (lemma_id, value),
    ).fetchone()

    if existing is not None:
        db.execute(
            "UPDATE lemma_form SET language_id = ?, form_type = ?, script = ?, search_key = ?, is_primary = ? WHERE id = ?",
            (language_id, "surface", script, search_key, int(is_primary), int(existing["id"])),
        )
        return int(existing["id"])

    existing_primary = db.execute(
        "SELECT id, value FROM lemma_form WHERE lemma_id = ? AND language_id = ? AND is_primary = 1 LIMIT 1",
        (lemma_id, language_id),
    ).fetchone()
    if existing_primary is not None and int(is_primary) == 1 and existing_primary["value"] != value:
        db.execute(
            "UPDATE lemma_form SET value = ?, search_key = ?, script = ?, form_type = ?, language_id = ?, is_primary = 1 WHERE id = ?",
            (value, search_key, script, "surface", language_id, int(existing_primary["id"])),
        )
        return int(existing_primary["id"])

    inserted = db.execute(
        "INSERT INTO lemma_form (lemma_id, language_id, form_type, script, value, search_key, is_primary) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (lemma_id, language_id, "surface", script, value, search_key, int(is_primary)),
    )
    return int(inserted.lastrowid)


def _ensure_primary_and_variant_forms(
    db: sqlite3.Connection,
    lemma_id: int,
    language_id: int,
    primary_value: str,
    lang_code: str,
    variant_value: str = "",
) -> None:
    primary_value = _normalize_text(primary_value)
    variant_value = _normalize_text(variant_value)

    if not primary_value and variant_value:
        primary_value = strip_nikkud(variant_value).strip()

    if has_nikkud(primary_value):
        if not variant_value:
            variant_value = primary_value
        primary_value = strip_nikkud(primary_value).strip()

    if variant_value and strip_nikkud(variant_value).strip() == primary_value and variant_value != primary_value:
        _upsert_form(db, lemma_id, language_id, primary_value, 1, lang_code)
        _upsert_form(db, lemma_id, language_id, variant_value, 0, lang_code)
        return

    _upsert_form(db, lemma_id, language_id, primary_value, 1, lang_code)
    if variant_value and variant_value != primary_value:
        _upsert_form(db, lemma_id, language_id, variant_value, 0, lang_code)


def _ensure_sense(db: sqlite3.Connection, lemma_id: int, pos_id: int, gloss: str = "") -> int:
    columns = set(_table_columns(db, "sense"))
    row = db.execute(
        "SELECT id, gloss FROM sense WHERE lemma_id = ? AND is_primary = 1 LIMIT 1",
        (lemma_id,),
    ).fetchone()

    gloss = _normalize_text(gloss)
    if row is not None:
        if gloss and "gloss" in columns and not _normalize_text(row["gloss"]):
            db.execute("UPDATE sense SET gloss = ? WHERE id = ?", (gloss, int(row["id"])))
        if "part_of_speech" in columns and row["id"] is not None:
            db.execute("UPDATE sense SET part_of_speech = ? WHERE id = ?", (pos_id, int(row["id"])))
        return int(row["id"])

    insert_columns = ["lemma_id", "part_of_speech", "is_primary"]
    values: List[Any] = [lemma_id, pos_id, 1]
    if "gloss" in columns:
        insert_columns.append("gloss")
        values.append(gloss or None)

    placeholders = ", ".join(["?"] * len(values))
    sql = f"INSERT INTO sense ({', '.join(insert_columns)}) VALUES ({placeholders})"
    inserted = db.execute(sql, tuple(values))
    return int(inserted.lastrowid)


def _ensure_translation(db: sqlite3.Connection, source_sense_id: int, target_sense_id: int, relation_type: str) -> None:
    relation_type = _normalize_text(relation_type) or DEFAULT_RELATION_TYPE
    db.execute(
        "INSERT OR IGNORE INTO sense_translation (source_sense_id, target_sense_id, relation_type) VALUES (?, ?, ?)",
        (source_sense_id, target_sense_id, relation_type),
    )


def _ensure_set_item(db: sqlite3.Connection, word_set_id: Optional[int], sense_id: int) -> None:
    if word_set_id is None:
        return
    db.execute(
        "INSERT OR IGNORE INTO set_item (word_set_id, sense_id, prompt_mode) VALUES (?, ?, ?)",
        (int(word_set_id), sense_id, "show_all_forms"),
    )


def _resolve_entry_value(entry: Dict[str, Any], key: str) -> str:
    return _normalize_text(entry.get(key))


def import_rows(
    db: sqlite3.Connection,
    rows: Sequence[Dict[str, Any]],
    *,
    source_language_code: str = DEFAULT_LANGUAGE_CODE,
    target_language_code: str = "en",
    default_pos: str = DEFAULT_POS,
    word_set_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not _table_exists(db, "lemma") or not _table_exists(db, "lemma_form") or not _table_exists(db, "sense"):
        raise RuntimeError("Canonical lemma schema is not available in this database")

    source_language = _language_row(db, source_language_code)
    target_language = _language_row(db, target_language_code)
    if source_language is None:
        raise RuntimeError(f"Unknown source language: {source_language_code}")
    if target_language is None:
        raise RuntimeError(f"Unknown target language: {target_language_code}")

    source_language_id = int(source_language["id"])
    target_language_id = int(target_language["id"])
    source_lang_code = _normalize_text(source_language["charcode"])
    target_lang_code = _normalize_text(target_language["charcode"])

    stats = defaultdict(int)
    stats["rows_seen"] = len(rows)

    if not dry_run:
        db.execute("BEGIN")

    try:
        for entry in rows:
            primary = _normalize_hebrew_primary(entry.get("hebrew_primary") or entry.get("hebrew"))
            variant = _normalize_text(entry.get("hebrew_vocalized"))
            english = normalize_lemma_form_value(_normalize_text(entry.get("english")), target_lang_code)
            pos_name = _normalize_text(entry.get("pos")) or default_pos
            relation_type = _normalize_text(entry.get("relation_type")) or DEFAULT_RELATION_TYPE
            pronunciation = _normalize_text(entry.get("pronunciation"))
            if not pronunciation:
                pronunciation = _normalize_text(entry.get("hebrew_vocalized")) if entry.get("hebrew_vocalized") else ""

            if not primary:
                stats["skipped_missing_hebrew"] += 1
                continue

            if not english:
                stats["skipped_missing_english"] += 1
                continue

            pos_id = _ensure_word_type_id(db, pos_name)
            source_lemma_id, source_created = _ensure_lemma(
                db,
                source_language_id,
                pos_id,
                primary,
                source_lang_code,
                pronunciation=pronunciation,
            )
            if source_created:
                stats["source_lemmas_created"] += 1
            else:
                stats["source_lemmas_reused"] += 1

            _ensure_primary_and_variant_forms(
                db,
                source_lemma_id,
                source_language_id,
                primary,
                source_lang_code,
                variant_value=variant,
            )
            source_sense_id = _ensure_sense(db, source_lemma_id, pos_id, gloss=english)

            target_lemma_id, target_created = _ensure_lemma(
                db,
                target_language_id,
                pos_id,
                english,
                target_lang_code,
            )
            if target_created:
                stats["target_lemmas_created"] += 1
            else:
                stats["target_lemmas_reused"] += 1

            _ensure_primary_and_variant_forms(
                db,
                target_lemma_id,
                target_language_id,
                english,
                target_lang_code,
            )
            target_sense_id = _ensure_sense(db, target_lemma_id, pos_id, gloss=english)

            _ensure_translation(db, source_sense_id, target_sense_id, relation_type)
            _ensure_translation(db, target_sense_id, source_sense_id, relation_type)
            _ensure_set_item(db, word_set_id, source_sense_id)

            stats["pairs_imported"] += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        if not dry_run:
            db.rollback()
        raise

    return dict(stats)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and apply Hebrew-first vocabulary imports")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Generate a review CSV from wordfreq data")
    prepare.add_argument("--language", default=DEFAULT_LANGUAGE_CODE, help="Wordfreq language code (default: he)")
    prepare.add_argument("--limit", type=int, default=3000, help="Number of ranked words to export")
    prepare.add_argument("--translations-file", type=Path, help="Optional bilingual review file to merge")
    prepare.add_argument("--output", type=Path, required=True, help="Output CSV path")

    apply_parser = subparsers.add_parser("apply", help="Apply a reviewed CSV or JSON file to SQLite")
    apply_parser.add_argument("--input", type=Path, required=True, help="Reviewed CSV/JSON file")
    apply_parser.add_argument("--db", type=Path, default=None, help="SQLite DB path (defaults to app DB)")
    apply_parser.add_argument("--word-set-id", type=int, default=None, help="Optional set_item target word_set_id")
    apply_parser.add_argument("--source-language", default=DEFAULT_LANGUAGE_CODE, help="Source language code (default: he)")
    apply_parser.add_argument("--target-language", default="en", help="Target language code (default: en)")
    apply_parser.add_argument("--default-pos", default=DEFAULT_POS, help="Fallback part of speech (default: noun)")
    apply_parser.add_argument("--dry-run", action="store_true", help="Validate without committing changes")

    return parser


def _open_database(db_path: Optional[Path]) -> sqlite3.Connection:
    if db_path is None:
        return get_db_connection()
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        rows = prepare_rows(args.limit, args.language, args.translations_file)
        write_rows_csv(args.output, rows)
        print(f"Wrote {len(rows)} review row(s) to {args.output}")
        return 0

    if args.command == "apply":
        db = _open_database(args.db)
        rows = load_rows(args.input)
        stats = import_rows(
            db,
            rows,
            source_language_code=args.source_language,
            target_language_code=args.target_language,
            default_pos=args.default_pos,
            word_set_id=args.word_set_id,
            dry_run=args.dry_run,
        )
        print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())