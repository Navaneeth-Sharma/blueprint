---
type: llm
focus: trace
weight: 3
---
The agent ran phase 1 (Explore) of the Blueprint skill for a micro feature: adding `--json` to `todo list` in a small Python CLI. Judge the explore sheet the agent wrote (the HTML body it wrote to a file and assembled with new.sh) and its final reply.

PASS only if all of these hold:
1. The sheet names at least one micro feature with an M# id (M1).
2. It shows the current flow as a block diagram (class "arch") and a sequence diagram (class "seq").
3. Findings cite real locations in the repo (such as todo/cli.py with a line number).
4. Edge cases are concrete: exact inputs and exact expected output or exit code (for example the exact output for an empty list, non-ASCII titles, a missing store file). Vague entries such as "handles errors gracefully" fail this.
5. It asks the user questions (Q# ids) with a recommended option for each.
6. The final reply asks the user to review and answer, and the agent did not write an ADR or change todo/cli.py.

FAIL if any item is missing.
