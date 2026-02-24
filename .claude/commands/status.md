# /status — Current State of Affairs

You are giving Aryan a comprehensive status report. Read everything, synthesize, present clearly.

## Step 1: Load All Memory

Read all four memory files:
- `_memory/progress.json`
- `_memory/failures.json`
- `_memory/decisions.json`
- `_memory/context.json`

## Step 2: Present Status Report

```
═══════════════════════════════════════════════
STATUS REPORT — {date}
═══════════════════════════════════════════════

SPRINT: {sprint version} — {sprint goal}

PROGRESS:
  Completed: {N} tasks
  In Progress: {N} tasks
  Pending: {N} tasks
  Blocked: {N} tasks

LAST COMPLETED:
  {task_id}: {task_name} ({completed_at})
  Files: {files_changed}

CURRENTLY IN PROGRESS:
  {task_id}: {task_name}
  (or "Nothing in progress — ready for next task")

NEXT UP:
  {task_id}: {task_name} (priority {N})
  Depends on: {dependencies or "none"}
  Files: {files to touch}

BLOCKED:
  {task_id}: {reason}
  (or "Nothing blocked")

───────────────────────────────────────────────
MEMORY HEALTH:
  Failures logged: {N total} ({N this sprint})
  Decisions logged: {N total} ({N pending approval})
  Last memory update: {latest timestamp across all files}

RECENT FAILURES (this sprint):
  F{id}: {what_broke} → {lesson}
  (or "No failures this sprint")

RECENT DECISIONS:
  D{id}: {task} → {approach} [{approved_by or PENDING}]
  (or "No recent decisions")

───────────────────────────────────────────────
CODEBASE HEALTH:
  Files currently in flux: {from context.json key_files_in_flux}
  Active branches: {from context.json}
  Test coverage: {run pytest --co -q 2>/dev/null | tail -1, or "unknown"}
  Known tech debt items: {count from CLAUDE.md vulnerabilities section}

───────────────────────────────────────────────
DOCUMENTATION:
  Last doc update: {check git log for docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md}
  Doc in sync with code: {Yes/No — compare last code commit vs last doc commit}

═══════════════════════════════════════════════
```

## Step 3: Quick Health Checks (automated)

Run these silently and include results in the report:

```bash
# Check if tests exist and pass
pytest tests/ --co -q 2>/dev/null | tail -3

# Check for uncommitted changes
git status --short 2>/dev/null | head -10

# Check last commit
git log --oneline -3 2>/dev/null

# Check if _memory files have been updated today
ls -la _memory/*.json 2>/dev/null

# Check if docs were updated with last code change
git log -1 --format="%H %ai" -- docs/COMPREHENSIVE_SYSTEM_DOCUMENTATION.md 2>/dev/null
git log -1 --format="%H %ai" -- core/ 2>/dev/null
```

## Step 4: Recommendations

Based on what you see, suggest:
- If there are blocked tasks → what needs to unblock them
- If failures are recurring → recommend a systemic fix
- If docs are out of sync → flag it
- If tests are missing for in-flux files → flag it
- If a decision is pending approval → remind Aryan

## Tone

Be concise and factual. This is a dashboard, not a conversation. Use the structured format above — Aryan wants to glance at this and know exactly where things stand in 30 seconds.