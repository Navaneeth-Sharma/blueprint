#!/usr/bin/env python3
"""Lint Blueprint sheets before a review gate.

usage: python3 check.py <record-dir | sheet.html> ...

Prints `file:line: error|warn: message`. Exits 1 if any error was found.
Warnings never fail: they flag things a reviewer should look at.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SHEETS = ("explore.html", "adr.html", "build.html")
SHEET_NO = {"explore.html": "1", "adr.html": "2", "build.html": "3"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Per micro feature (M#). Past these, a micro feature has probably grown into several.
LIMITS = {"D": 5, "E": 20, "C": 16, "T": 8}
OPEN_STATUSES = {"open", "planned"}
INT = re.compile(r"^-?\d+$")
TEMPLATE = Path(__file__).with_name("template.html")


class Node:
    def __init__(self, tag, attrs, line):
        self.tag, self.attrs, self.line, self.children = tag, attrs, line, []

    @property
    def classes(self):
        return self.attrs.get("class", "").split()

    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.walk()

    def elements(self):
        return [c for c in self.children if isinstance(c, Node)]

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def find(self, pred):
        return [n for n in self.walk() if pred(n)]


class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, 0)
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or "" for k, v in attrs}, self.getpos()[0])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def known_classes():
    style = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(), re.S).group(1)
    style = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
    return set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", style))


def num(value, default=None):
    return int(value) if INT.match(str(value).strip()) else default


def style_vars(node):
    """Parse style="--n:5; --from:0" into {"--n": "5", "--from": "0"}."""
    out = {}
    for decl in filter(None, (d.strip() for d in node.attrs.get("style", "").split(";"))):
        prop, _, value = decl.partition(":")
        out[prop.strip()] = value.strip()
    return out


class Sheet:
    def __init__(self, path, report):
        self.path, self.name, self.report = path, path.name, report
        tree = Tree(path.read_text(encoding="utf-8"))
        mains = tree.root.find(lambda n: n.tag == "main")
        self.main = mains[0] if mains else None
        self.ids, self.defined = {}, {}
        if not self.main:
            self.err(1, "no <main> element; build sheets with new.sh")
            return
        self.msgs = self.main.find(lambda n: "msg" in n.classes)
        for i, m in enumerate(self.msgs, 1):
            self.ids[f"S{i}"] = m
        for n in self.main.walk():
            if "id" in n.attrs and "msg" not in n.classes:
                if n.attrs["id"] in self.ids:
                    self.err(n.line, f'duplicate id "{n.attrs["id"]}"')
                self.ids[n.attrs["id"]] = n
        for i in self.ids:
            m = re.match(r"^([A-Z])(\d+)$", i)
            if m:
                self.defined.setdefault(m.group(1), set()).add(i)

    def err(self, line, msg):
        self.report.append((f"{self.path}:{line}", "error", msg))

    def warn(self, line, msg):
        self.report.append((f"{self.path}:{line}", "warn", msg))

    # ---- single-sheet rules ----

    def check(self, classes):
        if not self.main:
            return
        self.check_title_block()
        self.check_markup(classes)
        self.check_sections()
        self.check_links()
        self.check_sequences()
        self.check_questions()
        self.check_arch()
        self.check_tables()
        self.check_size()

    def check_title_block(self):
        first = next(iter(self.main.elements()), None)
        if not first or first.tag != "header" or "tb" not in first.classes:
            self.err(self.main.line, 'the first element in <main> must be the title block <header class="tb">')
            return
        for cls, what in (("tb-no", "record number"), ("tb-meta", "meta fields"), ("tb-phases", "phase stepper")):
            if not first.find(lambda n: cls in n.classes):
                self.err(first.line, f"title block is missing its {what} (.{cls})")
        if not first.find(lambda n: n.tag == "h1"):
            self.err(first.line, "title block is missing its <h1>")
        phases = first.find(lambda n: "tb-phases" in n.classes)
        if phases:
            items = [li for li in phases[0].elements() if li.tag == "li"]
            if len(items) != 3:
                self.err(phases[0].line, f"phase stepper needs 3 steps, found {len(items)}")
            if sum("now" in li.classes for li in items) > 1:
                self.err(phases[0].line, "more than one phase is marked .now")
        sheet = first.find(lambda n: "tb-sheet" in n.classes)
        want = SHEET_NO.get(self.name)
        if sheet and want:
            got = re.search(r"\d", sheet[0].text())
            if not got or got.group() != want:
                self.warn(sheet[0].line, f"{self.name} should say Sheet {want}/3")

    def check_markup(self, classes):
        for n in self.main.walk():
            if n.tag in ("style", "link", "script"):
                self.err(n.line, f"<{n.tag}> inside the sheet; the theme is fixed, use template classes")
            for c in n.classes:
                if c not in classes:
                    self.err(n.line, f'class "{c}" is not in the theme; copy markup from template.html')
            if "style" in n.attrs:
                bad = [p for p, v in style_vars(n).items() if p not in ("--n", "--from", "--to") or not INT.match(v)]
                if bad:
                    self.err(n.line, f"inline style may only set integer --n/--from/--to, found {', '.join(bad)}")
            if "msg" in n.classes and "id" in n.attrs:
                self.warn(n.line, "remove the id on .msg: step ids S1..Sn are assigned by position")

    def check_sections(self):
        for s in self.main.find(lambda n: n.tag == "section"):
            kids = s.elements()
            if not s.attrs.get("id"):
                self.err(s.line, "<section> needs an id so the sheet index can link to it")
            if not kids or kids[0].tag != "h2":
                self.err(s.line, "<section> must start with an <h2>")

    def check_links(self):
        for a in self.main.find(lambda n: n.tag == "a" and "href" in n.attrs):
            href = a.attrs["href"]
            if re.match(r"^[a-z][\w+.-]*:", href, re.I):
                continue  # http:, mailto:, ...
            page, _, frag = href.partition("#")
            if page and page not in SHEETS:
                continue  # some other local file; not ours to judge
            if page and page != self.name:
                other = self.path.with_name(page)
                if not other.exists():
                    (self.err if frag else self.warn)(a.line, f"links to {page}, which doesn't exist yet")
                    continue
                target_ids = Sheet.cached(other, self.report).ids
            else:
                target_ids = self.ids
            if frag and frag not in target_ids:
                self.err(a.line, f'broken link "{href}": no element with id "{frag}"')
            if "id" in a.classes and frag and a.text().strip() != frag:
                self.err(a.line, f'ID chip says "{a.text().strip()}" but points at #{frag}')

    def check_sequences(self):
        for fig in self.main.find(lambda n: "seq" in n.classes):
            n = num(style_vars(fig).get("--n"), 0)
            if n < 2:
                self.err(fig.line, 'sequence diagram needs style="--n:<actor count>" (2 or more)')
                continue
            actors = fig.find(lambda x: "seq-actors" in x.classes)
            count = len(actors[0].elements()) if actors else 0
            if count != n:
                self.err(fig.line, f"--n is {n} but .seq-actors has {count} actors")
            for m in fig.find(lambda x: "msg" in x.classes or "seq-note" in x.classes):
                v = style_vars(m)
                f = num(v.get("--from"))
                t = num(v.get("--to"), f)
                if f is None or t is None:
                    self.err(m.line, "step needs integer --from (and --to)")
                    continue
                if not (0 <= f < n and 0 <= t < n):
                    self.err(m.line, f"--from/--to must be 0..{n - 1}, got {f}/{t}")
                if "msg" in m.classes and "self" not in m.classes:
                    if "--to" not in v:
                        self.err(m.line, "message is missing --to (use class self for a call to itself)")
                    elif f == t:
                        self.err(m.line, "--from equals --to; use class self for a call to itself")
                if "seq-note" in m.classes and t < f:
                    self.err(m.line, "note needs --to >= --from")

    def check_questions(self):
        questions = self.main.find(lambda n: n.tag == "fieldset" and "q" in n.classes)
        for q in questions:
            if not re.match(r"^Q\d+$", q.attrs.get("id", "")):
                self.err(q.line, f'question needs id="Q<n>", got "{q.attrs.get("id", "")}"')
            for r in q.find(lambda n: n.tag == "input" and n.attrs.get("type") == "radio"):
                if not r.attrs.get("id"):
                    self.err(r.line, "every answer radio needs an id (like Q1-A) so saved picks can be restored")
        if questions:
            for need, what in (("answers-status", "status line"), ("copy-answers", "Copy answers button"), ("answers-out", "answers output")):
                if need not in self.ids:
                    self.warn(questions[0].line, f"questions have no #{need} ({what}); copy the answers block from template.html")

    def check_arch(self):
        for t in self.main.find(lambda n: "tier" in n.classes):
            if not t.attrs.get("data-tier"):
                self.err(t.line, 'tier needs a data-tier="<name>" label')

    def check_tables(self):
        for table in self.main.find(lambda n: n.tag == "table"):
            head = table.find(lambda n: n.tag == "thead")
            body_rows = [r for tb in table.find(lambda n: n.tag == "tbody") for r in tb.elements() if r.tag == "tr"]
            head_rows = [r for r in head[0].elements() if r.tag == "tr"] if head else []
            width = sum(num(c.attrs.get("colspan", 1), 1) for c in head_rows[0].elements()) if head_rows else None
            for r in body_rows:
                cells = [c for c in r.elements() if c.tag in ("td", "th")]
                if width and sum(num(c.attrs.get("colspan", 1), 1) for c in cells) != width:
                    self.err(r.line, f"row has {len(cells)} cells but the header has {width} columns")
            kind = "cases" if "cases" in table.classes else "matrix" if "matrix" in table.classes else None
            if not kind:
                continue
            prefix = "E" if kind == "cases" else "C"
            if kind == "matrix" and head_rows:
                last = [c.text().strip().lower() for c in head_rows[-1].elements()][-2:]
                if len(last) < 2 or not last[0].startswith("expected") or not last[1].startswith("result"):
                    self.err(table.line, "case matrix: the last two columns must be Expected and Result")
            for r in body_rows:
                rid = r.attrs.get("id", "")
                if not re.match(rf"^{prefix}\d+$", rid):
                    self.err(r.line, f'{kind} row needs id="{prefix}<n>", got "{rid}"')
                cells = [c for c in r.elements() if c.tag in ("td", "th")]
                pills = cells[-1].find(lambda n: "pill" in n.classes) if cells else []
                if not pills:
                    self.err(r.line, f"{rid or kind + ' row'} has no status pill in its last column")
                elif self.name == "build.html" and pills[0].text().strip().lower() in OPEN_STATUSES:
                    self.err(r.line, f'{rid} is still "{pills[0].text().strip()}"; build needs pass, fail or untested')

    def check_size(self):
        features = max(1, len(self.defined.get("M", ())))
        for prefix, limit in LIMITS.items():
            count = len(self.defined.get(prefix, ()))
            if count > limit * features:
                self.warn(self.main.line, f"{count} {prefix}# items for {features} micro feature(s), limit {limit} each; split into more micro features")

    _cache = {}

    @classmethod
    def cached(cls, path, report):
        key = path.resolve()
        if key not in cls._cache:
            cls._cache[key] = Sheet(path, [])  # parse only; its own findings are reported when it is checked
        return cls._cache[key]


def record_number(sheet):
    no = sheet.main.find(lambda n: "tb-no" in n.classes) if sheet.main else []
    m = re.match(r"\s*(\S+)", no[0].text()) if no else None
    return m.group(1) if m else None


def mentions(sheet, ident):
    return ident in sheet.ids or bool(sheet.main.find(lambda n: n.tag == "a" and n.attrs.get("href", "").endswith("#" + ident)))


def check_record(sheets, report):
    by = {s.name: s for s in sheets if s.main}
    numbers = {s.name: record_number(s) for s in by.values()}
    if len(set(numbers.values())) > 1:
        report.append((str(next(iter(by.values())).path.parent), "error", f"record numbers differ across sheets: {numbers}"))
    adr, explore, build = by.get("adr.html"), by.get("explore.html"), by.get("build.html")
    if adr and build:
        for prefix in "ETC":
            for ident in sorted(adr.defined.get(prefix, ()), key=lambda i: int(i[1:])):
                if not mentions(build, ident):
                    build.err(build.main.line, f"{ident} is in adr.html but build.html never mentions it")
    if explore and adr:
        for prefix, what in (("Q", "answers"), ("M", "micro features"), ("E", "edge cases")):
            for ident in sorted(explore.defined.get(prefix, ()), key=lambda i: int(i[1:])):
                if not mentions(adr, ident):
                    adr.warn(adr.main.line, f"{ident} from explore.html is missing from the ADR {what}")


def main(argv):
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    report, classes = [], known_classes()
    for arg in argv:
        p = Path(arg)
        if p.is_dir():
            files = [p / s for s in SHEETS if (p / s).exists()]
            if not files:
                report.append((str(p), "error", "no explore.html, adr.html or build.html in this folder"))
        elif p.exists():
            files = [p]
        else:
            report.append((arg, "error", "no such file or folder"))
            continue
        sheets = [Sheet(f, report) for f in files]
        for s in sheets:
            s.check(classes)
        if p.is_dir():
            check_record(sheets, report)
    for where, level, msg in report:
        print(f"{where}: {level}: {msg}")
    errors = sum(level == "error" for _, level, _ in report)
    warns = len(report) - errors
    print(f"{errors} error{'s' * (errors != 1)}, {warns} warning{'s' * (warns != 1)}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
