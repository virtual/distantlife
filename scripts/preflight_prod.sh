#!/usr/bin/env bash
set -euo pipefail

DB_FILE="${DB_FILE:-distantlife.db}"
APP_ENTRY="${APP_ENTRY:-application.py}"
REDIS_URL_EFFECTIVE="${REDIS_URL:-redis://127.0.0.1:6379/0}"

pass() {
  printf "[PASS] %s\n" "$1"
}

fail() {
  printf "[FAIL] %s\n" "$1"
  exit 1
}

warn() {
  printf "[WARN] %s\n" "$1"
}

printf "Running Distant Life production preflight...\n"

command -v python >/dev/null 2>&1 || fail "python is not available on PATH"
pass "python is available"

[[ -f "$APP_ENTRY" ]] || fail "missing app entry file: $APP_ENTRY"
pass "app entry file present: $APP_ENTRY"

[[ -n "${SECRET_KEY:-}" ]] || fail "SECRET_KEY is not set"
[[ "${#SECRET_KEY}" -ge 16 ]] || fail "SECRET_KEY is set but too short (< 16 chars)"
pass "SECRET_KEY is set"

[[ -f "$DB_FILE" ]] || fail "database file not found: $DB_FILE"
[[ -r "$DB_FILE" ]] || fail "database file is not readable: $DB_FILE"
[[ -w "$DB_FILE" ]] || fail "database file is not writable: $DB_FILE"
pass "database file is present/readable/writable: $DB_FILE"

python - <<'PY' || fail "python dependency or runtime checks failed"
import os
import sqlite3
import sys

required_imports = [
    "flask",
    "flask_session",
    "flask_babel",
    "flask_limiter",
    "redis",
]

for mod in required_imports:
    __import__(mod)

db_file = os.environ.get("DB_FILE", "distantlife.db")
conn = sqlite3.connect(db_file)
conn.row_factory = sqlite3.Row

required_tables = ["users", "languages", "word_sets"]
for table in required_tables:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing table: {table}")

lemma_table = conn.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lemma'"
).fetchone()
set_item_table = conn.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='set_item'"
).fetchone()
if lemma_table is None or set_item_table is None:
    raise RuntimeError("database is not migrated to lemma schema (missing lemma/set_item)")

conn.close()
PY
pass "python imports and sqlite schema checks passed"

python - <<'PY' || fail "redis connection check failed"
import os
import redis

redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
client = redis.from_url(redis_url)
client.ping()
PY
pass "redis is reachable at ${REDIS_URL_EFFECTIVE}"

if [[ "${FLASK_ENV:-}" == "development" ]]; then
  warn "FLASK_ENV=development in production environment"
fi

printf "Preflight complete: ready to start the app.\n"