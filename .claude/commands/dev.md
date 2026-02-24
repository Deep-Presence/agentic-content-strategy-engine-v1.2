Pick and execute the highest-priority pending task using Test-Driven Development.

Steps:
1. Read `_memory/progress.json` — find the highest priority pending task whose dependencies are all completed.
2. Announce the task you're picking and present a Decision Brief:
   - What you'll build
   - Your approach and why
   - Alternatives you considered
   - Files you'll touch
3. **Wait for approval before proceeding.**
4. After approval, follow TDD:
   a. **Red** — Write the test first. It should fail.
   b. **Green** — Write the minimum code to make the test pass.
   c. **Refactor** — Clean up while keeping tests green.
5. Run the full relevant test suite to confirm nothing broke.
6. If any non-obvious decision comes up mid-implementation, pause and present another Decision Brief.
7. After completion:
   - Move the task from `pending` to `completed` in `_memory/progress.json`
   - Log any decisions in `_memory/decisions.json`
   - Log any failures in `_memory/failures.json`
   - Show a brief summary of what was done

If $ARGUMENTS is provided, use it as a specific task ID to work on instead of auto-picking.