#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d "venv" ]]; then
  python -m venv venv
fi

source venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export FLASK_APP=application
export FLASK_ENV=development

exec python -m flask --app application --debug run "$@"