---
type: llm
focus: { source: file, path: docs/adr/0001-json-output/adr.html }
weight: 3
---
This is the ADR sheet the Blueprint skill wrote after the user answered question Q1 ("Include completed items?") with B: No. The feature adds `--json` to `todo list` in a small Python CLI.

PASS only if all of these hold:
1. The decisions reflect the answer: the JSON output leaves out completed items (or the ADR records answer B and a decision that follows from it).
2. There is an answers table mapping Q1 to that answer.
3. Edge cases have exact expected results (exact JSON, exit codes, encodings), and each says which decision or step handles it.
4. The case matrix rows are concrete condition combinations with exact expected outcomes, and the last two columns are Expected and Result (Result "planned").
5. The plan has T# tasks, each naming the D# it implements and the E#/C# that prove it.
6. The status is Proposed.

FAIL if any item is missing or the ADR contradicts the answer.
