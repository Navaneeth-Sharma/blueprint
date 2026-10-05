---
type: regex
target: { source: file, path: docs/adr/0001-json-output/build.html }
pattern: 'class="pill">\s*(planned|open)\s*<'
match: not_contains
---

