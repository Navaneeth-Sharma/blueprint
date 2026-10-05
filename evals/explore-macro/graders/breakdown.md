---
type: llm
focus: trace
weight: 3
---
The user asked the Blueprint skill to explore a large change: turning a tiny todo CLI into a multi-user web app with accounts, shared lists and email reminders. The skill is supposed to accept changes of any size but break them into micro features and specify details per micro feature.

PASS only if all of these hold:
1. The explore sheet breaks the work into at least 3 micro features with M# ids, each with a one-line scope, what it depends on, and a rough size.
2. It asks the user (as a Q#) whether to keep one record or split into one record per micro feature, and recommends one.
3. Edge cases stay concrete (exact inputs and results) rather than generic.
4. The agent did not refuse the request, did not write any application code, and stopped for the user's answers.

FAIL otherwise.
