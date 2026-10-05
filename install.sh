#!/bin/sh
# Link the blueprint skill into your agents' skill folders, so `git pull` updates every agent at once.
# usage: ./install.sh                 Claude Code (~/.claude/skills) and omp (~/.omp/agent/skills), whichever exist
#        ./install.sh <skills-dir>...  any other agent that loads SKILL.md folders
set -e
src=$(cd "$(dirname "$0")/skills/blueprint" && pwd)
if [ $# -eq 0 ]; then
  if [ -d "$HOME/.claude" ]; then set -- "$@" "$HOME/.claude/skills"; fi
  if [ -d "$HOME/.omp/agent" ]; then set -- "$@" "$HOME/.omp/agent/skills"; fi
  if [ $# -eq 0 ]; then
    echo "install.sh: found neither ~/.claude nor ~/.omp/agent; pass a skills folder: ./install.sh <dir>" >&2
    exit 1
  fi
fi
for dir in "$@"; do
  dest="$dir/blueprint"
  mkdir -p "$dir"
  if [ -L "$dest" ]; then
    rm "$dest"
  elif [ -e "$dest" ]; then
    # Back up outside the skills folder, or the agent would load the backup as a second skill.
    backup="$HOME/.blueprint-backups/$(date +%Y%m%d%H%M%S)$(printf '%s' "$dir" | tr '/' '_')"
    mkdir -p "$HOME/.blueprint-backups"
    mv "$dest" "$backup"
    echo "moved the existing $dest to $backup"
  fi
  ln -s "$src" "$dest"
  echo "linked $dest -> $src"
done
