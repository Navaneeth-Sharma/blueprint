#!/usr/bin/env python3
"""Serve Blueprint records on this machine and save the answers people pick on an explore sheet.

usage: python3 serve.py <sheet.html | record-dir>   start (or reuse) the server and print the sheet's URL
       python3 serve.py --stop <sheet.html | record-dir>

One server per records folder (docs/adr). It runs in the background, listens on 127.0.0.1 only,
and exits after 4 hours without requests. Picking an answer on an explore sheet it serves writes
<record>/answers.json, which the agent reads in the decide phase.
"""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IDLE_SECONDS = int(os.environ.get("BLUEPRINT_SERVE_IDLE", 4 * 3600))
MAX_BODY = 64 * 1024
MAX_TEXT = 4000
QID = re.compile(r"^Q\d+$")
SHEETS = ("explore.html", "adr.html", "build.html")


def locate(arg):
    """Map a sheet or record folder to (records root, path of the page to open)."""
    p = Path(arg).resolve()
    if p.is_file():
        return p.parent.parent, f"{p.parent.name}/{p.name}"
    if p.is_dir() and any((p / s).exists() for s in SHEETS):
        return p.parent, f"{p.name}/"
    raise SystemExit(f"serve.py: {arg} is not a Blueprint sheet or record folder")


def state_file(root):
    key = hashlib.sha1(str(root).encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"blueprint-serve-{key}.json"


def read_state(root):
    try:
        return json.loads(state_file(root).read_text())
    except (OSError, ValueError):
        return None


def alive(root, state):
    if not state:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{state['port']}/__blueprint", timeout=1) as r:
            return r.read().decode() == str(root)
    except OSError:
        return False


def clean(value):
    return value if isinstance(value, str) and len(value) <= MAX_TEXT else None


def parse_answers(raw):
    """Validate a posted answers document; return the normalized dict or None."""
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    answers = doc.get("answers") if isinstance(doc, dict) else None
    if not isinstance(answers, dict) or len(answers) > 100:
        return None
    out = {}
    for qid, a in answers.items():
        if not QID.match(qid) or not isinstance(a, dict):
            return None
        fields = {k: clean(a.get(k, "")) for k in ("option", "label", "note")}
        if None in fields.values():
            return None
        out[qid] = fields
    text = clean(doc.get("text", ""))
    if text is None:
        return None
    return {"sheet": "explore", "answers": out, "text": text}


class Handler(SimpleHTTPRequestHandler):
    server_version = "blueprint"

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.server.last_request = time.monotonic()
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Blueprint", "1")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def record(self):
        """The record folder for /<record>/answers, or None."""
        m = re.fullmatch(r"/([A-Za-z0-9._-]+)/answers", self.path.split("?")[0])
        if not m or m.group(1) in (".", ".."):
            return None
        folder = (self.server.root / m.group(1)).resolve()
        if folder.parent != self.server.root or not (folder / "explore.html").is_file():
            return None
        return folder

    def local_request(self):
        """Refuse requests from other websites and DNS-rebinding hosts."""
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or origin.split("//")[-1] in hosts)

    def do_GET(self):
        if self.path == "/__blueprint":
            data = str(self.server.root).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.split("?")[0].endswith("/answers"):
            folder = self.record()
            if not folder:
                self.send_json(404, {"error": "not a record with an explore sheet"})
                return
            try:
                saved = json.loads((folder / "answers.json").read_text())
            except (OSError, ValueError):
                saved = {}
            self.send_json(200, saved)
            return
        super().do_GET()

    def do_POST(self):
        if not self.local_request():
            self.send_json(403, {"error": "answers can only be saved from this machine's own page"})
            return
        folder = self.record()
        if not folder:
            self.send_json(404, {"error": "not a record with an explore sheet"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self.send_json(415, {"error": "send application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            self.send_json(413, {"error": f"body must be 1 to {MAX_BODY} bytes"})
            return
        doc = parse_answers(self.rfile.read(length))
        if doc is None:
            self.send_json(400, {"error": "expected {answers: {Q1: {option, label, note}}, text}"})
            return
        doc["savedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tmp = folder / f".answers.{os.getpid()}.{threading.get_ident()}.tmp"
        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, folder / "answers.json")  # atomic: a reader never sees half a file
        self.send_json(200, {"saved": doc["savedAt"]})


def run(root):
    preferred = 47000 + int(hashlib.sha1(str(root).encode()).hexdigest(), 16) % 1000
    try:
        server = ThreadingHTTPServer(("127.0.0.1", preferred), lambda *a: Handler(*a, directory=str(root)))
    except OSError:
        server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=str(root)))
    server.root = root
    server.last_request = time.monotonic()
    state_file(root).write_text(json.dumps({"port": server.server_address[1], "pid": os.getpid(), "root": str(root)}))

    def watchdog():
        while time.monotonic() - server.last_request < IDLE_SECONDS:
            time.sleep(min(30, IDLE_SECONDS))
        server.shutdown()

    threading.Thread(target=watchdog, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    try:
        server.serve_forever()
    finally:
        server.server_close()
        state = read_state(root)
        if state and state.get("pid") == os.getpid():
            state_file(root).unlink(missing_ok=True)


def main(argv):
    if len(argv) == 2 and argv[0] == "--run":
        run(Path(argv[1]))
        return 0
    stop = bool(argv) and argv[0] == "--stop"
    args = argv[1:] if stop else argv
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root, page = locate(args[0])
    state = read_state(root)
    if stop:
        if alive(root, state):
            os.kill(state["pid"], signal.SIGTERM)
            print(f"stopped the server for {root}")
        state_file(root).unlink(missing_ok=True)
        return 0
    if not alive(root, state):
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--run", str(root)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        for _ in range(100):
            time.sleep(0.05)
            state = read_state(root)
            if alive(root, state):
                break
        else:
            print("serve.py: the server did not start", file=sys.stderr)
            return 1
    print(f"http://127.0.0.1:{state['port']}/{page}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
