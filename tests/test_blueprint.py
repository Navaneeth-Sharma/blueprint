"""Tests for new.sh, check.py and install.sh. Run: python3 -m unittest discover tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "blueprint"
FIXTURE = ROOT / "tests" / "fixtures" / "record"
SHEETS = ("explore", "adr", "build")


def run(cmd, stdin="", env=None, cwd=None):
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=env, cwd=cwd)


def new_sheet(out, title, body):
    return run(["sh", str(SKILL / "new.sh"), str(out), title], stdin=body)


def check(*paths):
    r = run([sys.executable, str(SKILL / "check.py"), *map(str, paths)])
    return r.returncode, r.stdout


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def build_record(self, edits=(), sheets=SHEETS):
        """Assemble the fixture record, applying (sheet, old, new) edits to the bodies first."""
        rec = self.tmp / "docs" / "adr" / "0001-json-output"
        for sheet in sheets:
            body = (FIXTURE / f"{sheet}.body.html").read_text()
            for target, old, new in edits:
                if target == sheet:
                    self.assertIn(old, body, f"edit target not found in {sheet}: {old!r}")
                    body = body.replace(old, new, 1)
            r = new_sheet(rec / f"{sheet}.html", "ADR-0001 JSON output", body)
            self.assertEqual(r.returncode, 0, r.stderr)
        return rec


class NewSh(Tmp):
    def test_builds_a_standalone_page(self):
        out = self.tmp / "rec" / "adr.html"
        r = new_sheet(out, "ADR-0002 Rate limits", "<section id=\"s\"><h2>S</h2></section>")
        self.assertEqual(r.returncode, 0, r.stderr)
        html = out.read_text()
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertTrue(html.rstrip().endswith("</html>"))
        self.assertEqual(html.count("<main>"), 1)
        self.assertEqual(html.count("</main>"), 1)
        self.assertIn("<title>ADR-0002 Rate limits</title>", html)
        self.assertIn('<section id="s"><h2>S</h2></section>\n</main>', html)

    def test_theme_is_copied_unchanged(self):
        out = self.tmp / "adr.html"
        new_sheet(out, "T", "<p>x</p>")
        head = lambda text: text.split("<main>")[0].split("<title>")[1].split("</title>", 1)[1]
        self.assertEqual(head(out.read_text()), head((SKILL / "template.html").read_text()))

    def test_title_is_escaped(self):
        cases = {
            "A & B": "A &amp; B",
            "pipe | slash \\ amp &": "pipe | slash \\ amp &amp;",
            "<script>x</script>": "&lt;script>x&lt;/script>",
            "two\nlines": "two lines",
            "quote \" and 'single'": "quote \" and 'single'",
            "unicode café ☕": "unicode café ☕",
        }
        for title, want in cases.items():
            with self.subTest(title=title):
                out = self.tmp / "t.html"
                self.assertEqual(new_sheet(out, title, "<p>x</p>").returncode, 0)
                self.assertIn(f"<title>{want}</title>", out.read_text())

    def test_body_is_copied_verbatim(self):
        body = "<p>100% of $HOME \\n `ticks` %s \\\\ café</p>\n\n<p>two</p>"
        out = self.tmp / "t.html"
        new_sheet(out, "T", body)
        self.assertIn(body, out.read_text())

    def test_refuses_empty_body(self):
        for body in ("", "   \n\t\n"):
            out = self.tmp / "empty.html"
            r = new_sheet(out, "T", body)
            self.assertEqual(r.returncode, 1)
            self.assertIn("nothing on stdin", r.stderr)
            self.assertFalse(out.exists())

    def test_refuses_a_full_page(self):
        for body in ("<!doctype html><p>x</p>", "<html><p>x</p></html>", "<main><p>x</p></main>",
                     "<body><p>x</p>", "<head><title>x</title></head>", '<MAIN class="x">'):
            with self.subTest(body=body):
                r = new_sheet(self.tmp / "full.html", "T", body)
                self.assertEqual(r.returncode, 1)
                self.assertIn("only what goes inside <main>", r.stderr)

    def test_header_tag_is_not_mistaken_for_head(self):
        r = new_sheet(self.tmp / "h.html", "T", '<header class="tb"></header>')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_usage_errors(self):
        for args in ([], ["only-one.html"], ["a.html", "b", "c"]):
            r = run(["sh", str(SKILL / "new.sh"), *args])
            self.assertEqual(r.returncode, 1)
            self.assertIn("usage:", r.stderr)

    def test_creates_nested_folders(self):
        out = self.tmp / "a" / "b" / "c" / "adr.html"
        self.assertEqual(new_sheet(out, "T", "<p>x</p>").returncode, 0)
        self.assertTrue(out.exists())

    def test_index_opens_the_furthest_phase(self):
        rec = self.tmp / "rec"
        index = rec / "index.html"
        new_sheet(rec / "explore.html", "T", "<p>x</p>")
        self.assertIn("url=explore.html", index.read_text())
        new_sheet(rec / "adr.html", "T", "<p>x</p>")
        self.assertIn("url=adr.html", index.read_text())
        new_sheet(rec / "explore.html", "T", "<p>revised</p>")
        self.assertIn("url=adr.html", index.read_text())
        new_sheet(rec / "build.html", "T", "<p>x</p>")
        self.assertIn("url=build.html", index.read_text())

    def test_no_index_for_other_file_names(self):
        new_sheet(self.tmp / "notes.html", "T", "<p>x</p>")
        self.assertFalse((self.tmp / "index.html").exists())

    def test_works_through_a_symlink_and_from_any_cwd(self):
        link = self.tmp / "skills" / "blueprint"
        link.parent.mkdir()
        link.symlink_to(SKILL)
        out = self.tmp / "out" / "adr.html"
        r = run(["sh", str(link / "new.sh"), str(out), "T"], stdin="<p>x</p>", cwd="/")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<style>", out.read_text())


class CheckPy(Tmp):
    def test_template_is_clean(self):
        code, out = check(SKILL / "template.html")
        self.assertEqual(code, 0, out)
        self.assertNotIn("error", out)

    def test_fixture_record_is_clean(self):
        code, out = check(self.build_record())
        self.assertEqual(code, 0, out)
        self.assertEqual(out, "")

    def test_each_rule(self):
        seq_adr = '<div class="msg" style="--from:1;--to:2">load()</div>'
        cases = [
            # (edits, expected level, expected message fragment)
            ([("adr", 'href="#D2">D2</a>).', 'href="#D9">D9</a>).')], "error", 'broken link "#D9"'),
            ([("adr", 'href="#D2">D2</a>).', 'href="#D2">D1</a>).')], "error", 'ID chip says "D1" but points at #D2'),
            ([("adr", '<div class="callout ok">', '<div class="callout danger">')], "error", 'class "danger" is not in the theme'),
            ([("adr", '<section id="consequences">', '<style>p{color:red}</style><section id="consequences">')], "error", "<style> inside the sheet"),
            ([("adr", '<section id="consequences">', '<script>alert(1)</script><section id="consequences">')], "error", "<script> inside the sheet"),
            ([("adr", 'style="--n:3"', 'style="--n:3;color:red"')], "error", "inline style may only set"),
            ([("adr", '<div class="node chg">', '<div class="node chg" style="width:10px">')], "error", "inline style may only set"),
            ([("adr", 'style="--n:3"', 'style="--n:4"')], "error", "--n is 4 but .seq-actors has 3 actors"),
            ([("adr", 'style="--n:3"', 'style="--n:x"')], "error", "sequence diagram needs"),
            ([("adr", seq_adr, '<div class="msg" style="--from:1;--to:5">load()</div>')], "error", "--from/--to must be 0..2"),
            ([("adr", seq_adr, '<div class="msg" style="--from:1;--to:1">load()</div>')], "error", "--from equals --to"),
            ([("adr", seq_adr, '<div class="msg" style="--from:1">load()</div>')], "error", "message is missing --to"),
            ([("adr", seq_adr, '<div class="msg" style="--from:a;--to:2">load()</div>')], "error", "step needs integer --from"),
            ([("adr", 'class="seq-note" style="--from:1;--to:2"', 'class="seq-note" style="--from:2;--to:1"')], "error", "note needs --to >= --from"),
            ([("adr", seq_adr, '<div class="msg" id="S2" style="--from:1;--to:2">load()</div>')], "warn", "remove the id on .msg"),
            ([("adr", 'data-tier="CLI"', "")], "error", "tier needs a data-tier"),
            ([("adr", '<section id="consequences">', "<section>")], "error", "<section> needs an id"),
            ([("adr", '<h2>Consequences</h2>', "<p>no heading</p>")], "error", "<section> must start with an <h2>"),
            ([("adr", '<section id="consequences">', '<section id="flows">')], "error", 'duplicate id "flows"'),
            ([("adr", '<td><span class="pill">planned</span></td></tr>\n      <tr id="E2">', "<td>—</td></tr>\n      <tr id=\"E2\">")], "error", "E1 has no status pill"),
            ([("adr", '<tr id="E2">', '<tr id="edge-2">')], "error", 'cases row needs id="E<n>"'),
            ([("adr", "<th>Expected</th><th>Result</th>", "<th>Outcome</th><th>Status</th>")], "error", "last two columns must be Expected and Result"),
            ([("adr", '<td class="y">yes</td><td class="y">yes</td>', '<td class="y">yes</td>')], "error", "row has 4 cells but the header has 5 columns"),
            ([("adr", '<header class="tb">', '<p>intro</p><header class="tb">')], "error", "first element in <main> must be the title block"),
            ([("adr", "<h1>JSON output for todo list</h1>", "")], "error", "title block is missing its <h1>"),
            ([("adr", '<span class="tb-no">ADR-0001</span>', "")], "error", "missing its record number"),
            ([("adr", '<li><span>Build</span>', '<li class="now"><span>Build</span>')], "error", "more than one phase is marked .now"),
            ([("adr", '<li><span>Build</span><small>next</small></li>', "")], "error", "phase stepper needs 3 steps, found 2"),
            ([("adr", "<b>2<small>/3</small></b>", "<b>1<small>/3</small></b>")], "warn", "adr.html should say Sheet 2/3"),
            ([("adr", 'href="explore.html#F1">F1', 'href="explore.html#F9">F9')], "error", 'broken link "explore.html#F9"'),
            ([("build", '<span class="pill">untested</span></td></tr>\n    </tbody>\n  </table></div>\n</section>\n\n<section id="matrix">',
               '<span class="pill">planned</span></td></tr>\n    </tbody>\n  </table></div>\n</section>\n\n<section id="matrix">')], "error", 'E3 is still "planned"'),
            ([("build", '<a class="id" href="adr.html#T2">T2</a>', "T-two")], "error", "T2 is in adr.html but build.html never mentions it"),
            ([("build", '<span class="tb-no">ADR-0001</span>', '<span class="tb-no">ADR-0002</span>')], "error", "record numbers differ"),
            ([("adr", '<a class="id" href="explore.html#Q1">Q1</a>', "Q-one")], "warn", "Q1 from explore.html is missing from the ADR answers"),
            ([("adr", '<li id="M1">', '<li id="M-one">')], "warn", "M1 from explore.html is missing"),
            ([("explore", '<input type="radio" name="Q1" id="Q1-B">', '<input type="radio" name="Q1">')], "error", "every answer radio needs an id"),
            ([("explore", '<fieldset class="q" id="Q1">', '<fieldset class="q" id="question-1">')], "error", 'question needs id="Q<n>"'),
            ([("explore", '<p class="answers-status" id="answers-status">Your picks are kept in this browser only.</p>', "")], "warn", "questions have no #answers-status"),
        ]
        for edits, level, fragment in cases:
            with self.subTest(fragment=fragment):
                rec = self.build_record(edits)
                code, out = check(rec)
                self.assertIn(f": {level}: ", out)
                self.assertIn(fragment, out)
                self.assertEqual(code, 1 if level == "error" else 0, out)
                shutil.rmtree(self.tmp / "docs")

    def test_links_to_sheets_not_written_yet(self):
        rec = self.build_record([("adr", '<li><span>Build</span>', '<li><a href="build.html#E1">Build</a>')], sheets=("explore", "adr"))
        code, out = check(rec)
        self.assertEqual(code, 1)
        self.assertIn("error: links to build.html, which doesn't exist yet", out)
        shutil.rmtree(self.tmp / "docs")
        rec = self.build_record([("adr", '<li><span>Build</span>', '<li><a href="build.html">Build</a>')], sheets=("explore", "adr"))
        code, out = check(rec)
        self.assertEqual(code, 0)
        self.assertIn("warn: links to build.html, which doesn't exist yet", out)

    def test_micro_feature_limits_scale_with_m_count(self):
        many = "".join(f'<li id="D{i}"><span class="id">D{i}</span><div><p>x</p></div></li>' for i in range(3, 8))
        edit = ("adr", '<li id="D2">', many + '<li id="D2">')
        code, out = check(self.build_record([edit]))
        self.assertIn("7 D# items for 1 micro feature(s), limit 5 each", out)
        self.assertEqual(code, 0)
        shutil.rmtree(self.tmp / "docs")
        second = '<li id="M2"><span class="id">M2</span><div><p>x</p></div></li>'
        code, out = check(self.build_record([edit, ("adr", '<li id="M1">', second + '<li id="M1">')]))
        self.assertNotIn("micro feature(s)", out)

    def test_single_sheet_and_bad_paths(self):
        rec = self.build_record()
        code, out = check(rec / "adr.html")
        self.assertEqual((code, out), (0, ""))
        code, out = check(self.tmp / "missing")
        self.assertEqual(code, 1)
        self.assertIn("no such file or folder", out)
        (self.tmp / "empty").mkdir()
        code, out = check(self.tmp / "empty")
        self.assertIn("no explore.html, adr.html or build.html", out)
        r = run([sys.executable, str(SKILL / "check.py")])
        self.assertEqual(r.returncode, 2)

    def test_hand_written_page_without_main(self):
        page = self.tmp / "adr.html"
        page.write_text("<html><body><p>hi</p></body></html>")
        code, out = check(page)
        self.assertEqual(code, 1)
        self.assertIn("no <main> element", out)

    def test_survives_broken_html(self):
        page = self.tmp / "adr.html"
        html = new_sheet(page, "T", (FIXTURE / "adr.body.html").read_text()) and page.read_text()
        page.write_text(html.replace("</section>", "", 3).replace("</table>", "") + "<div><span>")
        code, out = check(page)
        self.assertIn(code, (0, 1))
        self.assertNotIn("Traceback", out)


class ServePy(Tmp):
    def serve(self, *args, idle=60):
        env = {**os.environ, "BLUEPRINT_SERVE_IDLE": str(idle)}
        return run([sys.executable, str(SKILL / "serve.py"), *map(str, args)], env=env)

    def start(self, sheets=("explore",), idle=60):
        rec = self.build_record(sheets=sheets)
        r = self.serve(rec / f"{sheets[0]}.html", idle=idle)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.addCleanup(self.serve, "--stop", rec)
        url = r.stdout.strip()
        self.base = url.rsplit("/", 2)[0]
        return rec, url

    def request(self, path, body=None, headers=None, method=None):
        data = body.encode() if isinstance(body, str) else body
        req = urllib.request.Request(self.base + path, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, dict(r.headers), r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode()

    def post(self, body, **headers):
        return self.request("/0001-json-output/answers", body, {"Content-Type": "application/json", **headers})

    ANSWERS = '{"answers": {"Q1": {"option": "Q1-B", "label": "B. No", "note": "ship it"}}, "text": "Q1: B. No | note: ship it"}'

    def test_serves_the_sheet_and_reuses_the_server(self):
        rec, url = self.start()
        self.assertRegex(url, r"^http://127\.0\.0\.1:\d+/0001-json-output/explore\.html$")
        status, headers, html = self.request("/0001-json-output/explore.html")
        self.assertEqual(status, 200)
        self.assertIn("<main>", html)
        self.assertEqual(headers["Cache-Control"], "no-store")
        again = self.serve(rec)
        self.assertEqual(again.stdout.strip(), self.base + "/0001-json-output/")

    def test_saves_and_returns_answers(self):
        rec, _ = self.start()
        status, headers, body = self.request("/0001-json-output/answers")
        self.assertEqual((status, headers.get("X-Blueprint"), json.loads(body)), (200, "1", {}))
        status, _, body = self.post(self.ANSWERS)
        self.assertEqual(status, 200, body)
        saved = json.loads((rec / "answers.json").read_text())
        self.assertEqual(saved["answers"]["Q1"], {"option": "Q1-B", "label": "B. No", "note": "ship it"})
        self.assertEqual(saved["text"], "Q1: B. No | note: ship it")
        self.assertIn("savedAt", saved)
        self.assertEqual(json.loads(self.request("/0001-json-output/answers")[2])["answers"], saved["answers"])
        self.assertEqual([p.name for p in rec.iterdir() if p.name.startswith(".")], [])  # no temp files left

    def test_refuses_bad_writes(self):
        rec, _ = self.start()
        port = self.base.rsplit(":", 1)[1]
        cases = [
            (dict(body=self.ANSWERS, Origin="https://evil.example"), 403),
            (dict(body=self.ANSWERS, Host=f"evil.example:{port}"), 403),
            (dict(body="not json"), 400),
            (dict(body='{"answers": {"drop table": {}}, "text": ""}'), 400),
            (dict(body='{"answers": {"Q1": {"label": 5}}, "text": ""}'), 400),
            (dict(body='{"answers": {"Q1": {"note": "' + "x" * 5000 + '"}}, "text": ""}'), 400),
            (dict(body="x" * 70000), 413),
        ]
        for kwargs, want in cases:
            with self.subTest(want=want, headers={k: v for k, v in kwargs.items() if k != "body"}):
                body = kwargs.pop("body")
                self.assertEqual(self.post(body, **kwargs)[0], want)
        self.assertEqual(self.request("/0001-json-output/answers", self.ANSWERS, {"Content-Type": "text/plain"})[0], 415)
        for path in ("/../answers", "/nope/answers", "/0001-json-output/explore.html"):
            self.assertIn(self.request(path, self.ANSWERS, {"Content-Type": "application/json"})[0], (404, 501))
        self.assertFalse((rec / "answers.json").exists())

    def test_record_without_explore_sheet_has_no_answers(self):
        rec, _ = self.start(sheets=("explore", "adr"))
        (rec / "explore.html").unlink()
        self.assertEqual(self.post(self.ANSWERS)[0], 404)

    def test_stop_and_idle_exit(self):
        rec, _ = self.start()
        self.assertEqual(self.serve("--stop", rec).returncode, 0)
        with self.assertRaises(OSError):
            urllib.request.urlopen(self.base + "/__blueprint", timeout=1)
        shutil.rmtree(self.tmp / "docs")
        rec, _ = self.start(idle=1)
        time.sleep(3.5)  # no requests: any request would count as activity
        with self.assertRaises(OSError):
            urllib.request.urlopen(self.base + "/__blueprint", timeout=1)

    def test_rejects_things_that_are_not_sheets(self):
        (self.tmp / "empty").mkdir()
        r = self.serve(self.tmp / "empty")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not a Blueprint sheet or record folder", r.stderr)


class InstallSh(Tmp):
    def install(self, *args):
        env = {**os.environ, "HOME": str(self.tmp)}
        return run(["sh", str(ROOT / "install.sh"), *args], env=env)

    def test_links_into_existing_agents_only(self):
        (self.tmp / ".claude").mkdir()
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        link = self.tmp / ".claude" / "skills" / "blueprint"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), SKILL)
        self.assertFalse((self.tmp / ".omp").exists())

    def test_links_both_agents(self):
        (self.tmp / ".claude").mkdir()
        (self.tmp / ".omp" / "agent").mkdir(parents=True)
        self.assertEqual(self.install().returncode, 0)
        for d in (".claude/skills", ".omp/agent/skills"):
            self.assertEqual((self.tmp / d / "blueprint").resolve(), SKILL)

    def test_backs_up_a_real_folder_and_replaces_a_link(self):
        skills = self.tmp / ".claude" / "skills"
        (skills / "blueprint").mkdir(parents=True)
        (skills / "blueprint" / "SKILL.md").write_text("old copy")
        r = self.install()
        self.assertIn("moved the existing", r.stdout)
        self.assertEqual([p.name for p in skills.iterdir()], ["blueprint"])  # no backup left where agents look
        backups = list((self.tmp / ".blueprint-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "SKILL.md").read_text(), "old copy")
        self.assertEqual(self.install().returncode, 0)  # re-running replaces the link, no new backup
        self.assertEqual(len(list((self.tmp / ".blueprint-backups").iterdir())), 1)
        self.assertEqual((skills / "blueprint").resolve(), SKILL)

    def test_custom_target(self):
        target = self.tmp / "other-agent" / "skills"
        self.assertEqual(self.install(str(target)).returncode, 0)
        self.assertEqual((target / "blueprint").resolve(), SKILL)

    def test_no_agents_found(self):
        r = self.install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("found neither", r.stderr)


if __name__ == "__main__":
    unittest.main()
