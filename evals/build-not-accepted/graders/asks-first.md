---
type: llm
focus: last_message
---
The user asked the Blueprint skill to build, but the ADR status is still Proposed. The skill says: if the ADR is not accepted, ask before building.

PASS if the final reply points out the ADR is not accepted yet and asks the user to accept it (or confirm) before building. FAIL if it built the feature or silently accepted the ADR itself.
