Generate a comprehensive walkthrough of recent work done in this sprint.

1. Read `_memory/progress.json` to identify all completed and in-progress tasks for the current sprint.
2. Read `_memory/decisions.json` for decisions made during this sprint.
3. Read `_memory/failures.json` for any failures encountered.

For each completed task, explain:
- **What it does** — plain English, as if briefing someone who hasn't seen the code
- **How it works** — technical explanation: the key logic, data flow, and patterns used
- **Files changed** — list each file with a one-line description of the change
- **Key decisions** — choices made and why (pull from decisions.json)
- **Tests** — what test coverage was added

Then cover:
- **Architecture changes** — any structural shifts, with before/after if relevant
- **Failures & lessons** — what broke, what we learned
- **What's next** — upcoming tasks and priorities from progress.json
- **Open questions** — anything needing human input

Format this as a sprint review document and save to `sprints/{current_sprint}/review.md`.

If $ARGUMENTS is provided, scope the walkthrough to that specific topic or file path.
