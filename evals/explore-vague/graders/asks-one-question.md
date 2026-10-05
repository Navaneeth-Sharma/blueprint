---
type: llm
focus: last_message
---
The user invoked the Blueprint explore phase with only "make it better" on a small todo CLI. The skill says: if the topic is too vague to research, ask one question and stop, without writing a sheet.

PASS if the final reply asks the user a clarifying question about what "better" should mean (one question, possibly with a few example directions) and does not claim to have produced an explore sheet. FAIL if it picks a direction on its own and proceeds, or asks a long questionnaire.
