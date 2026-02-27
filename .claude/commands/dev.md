# /dev — Pick & Implement Highest Priority Task (TDD)

You are implementing the next task from the current sprint. Follow this exact process:

## Step 1: Load State
- Read `_memory/progress.json` — find the highest-priority pending task
- Read `_memory/failures.json` — check for relevant failure patterns
- Read `_memory/decisions.json` — check for relevant constraints
- Read the sprint PRD at `sprints/{current_sprint}/prd.md`

## Step 2: Announce the Task
Tell Aryan:
```
NEXT TASK: {task_id} — {task_name}
WHY THIS IS NEXT: {priority reasoning}
FILES I'LL TOUCH: {list}
ESTIMATED CHANGES: {brief description}
RISKS: {what could go wrong}
RELEVANT PAST FAILURES: {any matching patterns from failures.json}
RELEVANT DECISIONS: {any constraints from decisions.json}
```

**Wait for Aryan's approval before proceeding.**

## Step 3: Plan the Implementation
Before writing any code:
1. Read the target files to understand current state
2. Identify the exact functions/classes to modify or create
3. List the test cases you'll write
4. Draft the plan internally (don't present to Aryan yet)

## Step 3b: Consult Codex on the Plan

**Before presenting the plan to Aryan, run it through Codex for a second opinion.**

```bash
codex --exec 'You are reviewing an implementation plan for a Python data pipeline (8-step gap analysis for B2B content strategy). 

PROJECT CONTEXT:
- Python 3.12, asyncio, Pydantic v2, raw SDK clients (no LangChain)
- Pipeline steps: s1 (crawl+embed) → s2 (query gen) → s3 (search 4 AI platforms) → s4 (enrich citations) → s5 (embed) → s6 (analyze) → s7 (visualize) → s8 (report)
- Each step produces JSON artifacts consumed by the next step
- Backward compatibility with existing serialized artifacts is critical

TASK: {task_name}
FILES TO CHANGE: {file_list}

MY PLAN:
{your_drafted_plan}

Review this plan and tell me:
1. MISSED EDGE CASES — What could break that I haven't accounted for?
2. BLIND SPOTS — Are there downstream effects on other pipeline steps I haven't considered?
3. ALTERNATIVE APPROACHES — Is there a simpler or more robust way to achieve the same goal?
4. BACKWARD COMPAT — Will this break deserialization of existing JSON artifacts?
5. TEST GAPS — What test cases am I missing?

Be specific. Reference file names and function names where possible.'
```
**NOTE: Always use model 'gpt-5.3-codex' for codex with 'high' reasoning_effort.**

**After Codex responds, incorporate its feedback:**
- If Codex identifies a missed edge case → add it to the plan
- If Codex suggests a better approach → evaluate it honestly. If it's genuinely better, switch. If not, note why you're keeping your approach.
- If Codex flags a backward compat issue → add a migration/default-value step to the plan
- If Codex catches missing tests → add them to the test list

## Step 3c: Present Final Plan to Aryan

Present the plan WITH the Codex feedback incorporated:

```
IMPLEMENTATION PLAN:
1. [Step 1 — what you'll do and why]
2. [Step 2 — what you'll do and why]
3. [Step 3 — what you'll do and why]

TESTS I'LL WRITE:
- test_[name]: [what it validates]
- test_[name]: [what it validates]

CODEX REVIEW:
- Incorporated: [what Codex caught that you added to the plan]
- Rejected: [what Codex suggested that you didn't adopt, and why]
- No issues: [if Codex had nothing to add]

DECISION NEEDED? [Yes/No — if yes, present the decision format from CLAUDE.md]
```

**Wait for Aryan's approval of the plan.**

## Step 4: Write Tests First (TDD)

**Read `skills/tdd.md` before writing any test.** Follow its patterns exactly.

- Write the test file BEFORE the implementation
- Tests should initially fail (red phase)
- Run tests to confirm they fail for the right reason
- Use the correct test category: unit, contract, roundtrip, or regression (see skill)
- Use fixtures from `tests/fixtures/` — load with `load_fixture()` helper
- Mock all API calls — never make real HTTP or LLM calls in tests

## Step 5: Implement
- Write the minimal code to make tests pass (green phase)
- Follow all code standards from CLAUDE.md
- Check backward compatibility for any model changes

## Step 6: Refactor (if needed)
- Clean up without changing behavior
- Run tests again to confirm nothing broke

## Step 7: Verify
- Run the full test suite: `pytest tests/ -v`
- If modifying gap analysis: run with fixture data to verify output quality
- Check that existing serialized artifacts still load

## Step 8: Update Memory, Documentation & Backlog
```json
// Move task from pending → completed in progress.json
{
  "id": "T3",
  "task": "...",
  "sprint": "v3",
  "status": "done",
  "completed_at": "2026-02-15",
  "files_changed": ["..."]
}
```

If you made any architectural decisions, log them to `_memory/decisions.json`.
If anything broke along the way, log it to `_memory/failures.json`.

**Update `docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md`:**
- Find the section(s) matching what you changed (see mapping table in CLAUDE.md)
- Edit in-place — don't append to the bottom
- Add a changelog entry at the bottom of the doc
- Update the document date in the header

**Sync `.claude/sprints/pending/backlog.md`:**
- If this task resolved a backlog item → mark it `✅ RESOLVED {date}` and move to `## Resolved`
- If this task produced deferred work (code review items, follow-ups, tech debt) → add new `PB-{N}` entries
- Update "Last synced" date and "Total items" count

## Step 9: Brief Summary
Tell Aryan what you did:
```
COMPLETED: {task_id} — {task_name}
CHANGES:
- {file}: {what changed}
TESTS ADDED:
- {test_name}: {what it validates}
DECISIONS MADE: {any, or "none"}
ISSUES ENCOUNTERED: {any, or "none"}
READY FOR: /walkthrough for detailed review
```