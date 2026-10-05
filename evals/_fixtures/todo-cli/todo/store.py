"""Todo items live in one file: $TODO_FILE, or ~/.todo.store by default."""
import json
import os
from pathlib import Path


def path():
    return Path(os.environ.get("TODO_FILE", Path.home() / ".todo.store"))


def load():
    p = path()
    return json.loads(p.read_text()) if p.exists() else []


def save(items):
    path().write_text(json.dumps(items, indent=2))
