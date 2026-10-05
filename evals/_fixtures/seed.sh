#!/bin/bash
# Seed an eval workspace (the current directory) with a fixture project as a git repo,
# plus any Blueprint sheets named after it: explore, adr (accepted) or adr-proposed.
# usage: seed.sh [todo-cli|shorty] [explore] [answers] [adr|adr-proposed]
set -euo pipefail
fixtures=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$fixtures/../.." && pwd)
project=todo-cli
if [ $# -gt 0 ] && [ -d "$fixtures/$1" ]; then project=$1; shift; fi
cp -R "$fixtures/$project/." .
rec=docs/adr/0001-json-output
for sheet in "$@"; do
  case $sheet in
    explore) sh "$root/skills/blueprint/new.sh" "$rec/explore.html" "ADR-0001 JSON output" < "$root/tests/fixtures/record/explore.body.html" ;;
    adr) sh "$root/skills/blueprint/new.sh" "$rec/adr.html" "ADR-0001 JSON output" < "$root/tests/fixtures/record/adr.body.html" ;;
    answers) cat > "$rec/answers.json" <<'JSON'
{
  "sheet": "explore",
  "answers": {"Q1": {"option": "Q1-B", "label": "B. No", "note": "scripts only want open items"}},
  "text": "Q1: B. No | note: scripts only want open items",
  "savedAt": "2026-10-01T09:30:00+00:00"
}
JSON
      ;;
    adr-proposed) sed -e 's|<span class="pill pass">Accepted</span>|<span class="pill warn">Proposed</span>|' -e 's|<small>accepted</small>|<small>waiting for review</small>|' \
        "$root/tests/fixtures/record/adr.body.html" | sh "$root/skills/blueprint/new.sh" "$rec/adr.html" "ADR-0001 JSON output" ;;
  esac
done >/dev/null
git init -q
git add -A
git -c user.name=Eval -c user.email=eval@example.com commit -qm "todo CLI"
