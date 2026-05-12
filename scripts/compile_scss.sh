#!/usr/bin/env bash
set -e

# Compile styles.scss -> static/styles.css and main.scss -> static/overrides.css
if command -v npx >/dev/null 2>&1; then
  npx sass source/sass/styles.scss static/styles.css --no-source-map --style=compressed
else
  sass source/sass/styles.scss static/styles.css --no-source-map --style=compressed
fi

echo "SCSS compiled to static/styles.css and static/overrides.css"
