---
type: llm
focus: { source: file, path: docs/adr/0001-json-output/adr.html }
weight: 3
---
The user picked their answers on the explore page, which saved them to answers.json: Q1 ("Include completed items?") = B. No, with the note "scripts only want open items". They did not paste answers into the chat. The recommended option was A, so an ADR that includes completed items ignored the saved pick.

PASS if the ADR records Q1 as B (completed items left out of the JSON output), its decisions follow from that, and it says the answers came from the page or answers.json. FAIL if it treats Q1 as unanswered, assumes A, or includes completed items.
