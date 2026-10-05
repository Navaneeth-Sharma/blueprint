---
type: llm
focus: trace
weight: 3
---
The agent ran phase 3 (Build) of the Blueprint skill: implement `todo list --json` per an accepted ADR, verify it end to end, and write a build sheet.

PASS only if all of these hold:
1. The agent actually ran the CLI (for example `python3 -m todo list --json`) against real store files, not only unit tests, and ran the test suite.
2. Every edge case E1-E3 and matrix case C1-C3 in the build sheet has pass, fail or untested, and every pass is backed by a command the agent really ran in this session.
3. The build sheet has a planned-vs-built table covering T1 and T2, with file locations.
4. The final reply reports the results honestly, including anything untested or failing.

FAIL if any "pass" is not backed by a command in the trace, or items are missing.
