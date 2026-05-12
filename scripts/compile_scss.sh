#!/usr/bin/env bash
set -e

# Compile styles.scss -> static/proj04.css and main.scss -> static/overrides.css
if command -v npx >/dev/null 2>&1; then
  npx sass source/sass/styles.scss static/proj04.css --no-source-map --style=compressed
  npx sass source/sass/main.scss static/overrides.css --no-source-map --style=compressed
else
  sass source/sass/styles.scss static/proj04.css --no-source-map --style=compressed
  sass source/sass/main.scss static/overrides.css --no-source-map --style=compressed
fi

echo "SCSS compiled to static/proj04.css and static/overrides.css"
