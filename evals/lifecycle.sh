#!/bin/bash
# Run the whole Explore → Decide → Build lifecycle headless in a real agent, one fresh session per phase,
# then lint and render every sheet it wrote. Uses your agent login and costs model tokens.
#
# usage: evals/lifecycle.sh <claude|omp> <todo-cli|shorty> "<topic>" [workdir]
# The decide phase gets its answers the way a person would. By default (ANSWERS=page) a browser picks a
# non-recommended option on the served explore page, which saves it, and decide runs with nothing pasted.
# ANSWERS=paste presses "Copy answers" instead and pastes the text into the decide prompt.
set -euo pipefail
# Everything lives in main, so bash has parsed the whole script before running it and editing it mid-run is safe.
main() {
  here=$(cd "$(dirname "$0")" && pwd)
  root=$(cd "$here/.." && pwd)
  agent=$1 fixture=$2 topic=$3
  work=${4:-$(mktemp -d)}
  mkdir -p "$work" && cd "$work"
  bash "$here/_fixtures/seed.sh" "$fixture"
  log="$work/agent.log"
  echo "workdir: $work"

  ask() {
    echo "=== $1" | tee -a "$log"
    case $agent in
      claude) claude -p "$1" --permission-mode acceptEdits --output-format stream-json --verbose \
                --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Skill,Agent,TodoWrite,Artifact,ArtifactComments" >> "$log" 2>&1 ;;
      omp) omp -p --no-session --no-title --auto-approve --max-time 45m "$1" >> "$log" 2>&1 ;;
      *) echo "agent must be claude or omp" >&2; exit 2 ;;
    esac
  }
  invoke() { if [ "$agent" = claude ]; then echo "/blueprint $1"; else echo "Use the blueprint skill: $1"; fi; }

  ask "$(invoke "explore $topic")"
  explore=$(ls docs/adr/*/explore.html 2>/dev/null | head -1)
  [ -n "$explore" ] || { echo "no explore sheet was written; see $log" >&2; exit 1; }
  if [ "${ANSWERS:-page}" = paste ]; then
    answers=$(cd "$root" && node evals/_fixtures/answers.mjs "$work/$explore")
    printf 'answers:\n%s\n' "$answers"
    ask "$(invoke "decide") My answers, copied from the sheet:
  $answers"
  else
    url=$(python3 "$root/skills/blueprint/serve.py" "$work/$explore")
    picked=$(cd "$root" && node evals/_fixtures/answer-on-page.mjs "$url")
    echo "picked on $url -> $picked"
    [ -f "$(dirname "$explore")/answers.json" ] || { echo "the page did not save answers.json" >&2; exit 1; }
    ask "I've answered the questions on the page. $(invoke "decide")"
    q=${picked%%:*}
    echo "ADR answers row for $q:"; grep -o "$q[^<]*<[^>]*>[^<]*" "$(dirname "$explore")/adr.html" | head -3
  fi
  ask "I've reviewed the ADR and I accept it. $(invoke "build")"

  rec=$(dirname "$explore")
  status=0
  python3 "$root/skills/blueprint/check.py" "$rec" || status=1
  (cd "$root" && node tests/browser.mjs "$work/$rec"/{explore,adr,build}.html) || status=1
  exit $status
}
main "$@"
exit
