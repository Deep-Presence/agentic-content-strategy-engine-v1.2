# /prd — Sprint Planning & PRD Generation

You are helping Aryan plan a sprint. Follow this exact process:

## Step 1: Load Context
- Read `_memory/progress.json` — what's done, what's pending
- Read `_memory/context.json` — current sprint, constraints
- Read `_memory/failures.json` — patterns to avoid
- Read `_memory/decisions.json` — constraints from past decisions

## Step 2: Brainstorm with Aryan
Ask Aryan:
1. What's the goal for this sprint?
2. Any specific files or features to focus on?
3. Any new constraints or changes?

## Step 3: Generate Sprint PRD
Create a sprint PRD at `sprints/{sprint_version}/prd.md` with:

```markdown
# Sprint {version} — {goal}

## Sprint Goal
[One sentence describing what success looks like]

## Context
- Previous sprint: {what was accomplished}
- Key decisions carried forward: {from decisions.json}
- Known issues to address: {from failures.json}

## Tasks (ordered by priority)

### T1: [Task Name] (5-10 min)
- **What:** [Specific deliverable]
- **Why:** [Business/technical justification]
- **Files:** [Exact files to touch]
- **Acceptance criteria:** [How to verify it's done]
- **Risks:** [What could go wrong]
- **Depends on:** [Other task IDs, or "none"]

### T2: [Task Name] (5-10 min)
...

## Out of Scope
[What we're NOT doing this sprint and why]

## Definition of Done
- [ ] All tasks completed and tested
- [ ] _memory/ files updated
- [ ] No regressions in existing functionality
- [ ] Walkthrough written for all changes
```

## Step 4: Validate
- Each task should take 5-10 minutes of Claude Code execution time
- Tasks must be atomic — one clear deliverable each
- Tasks must be ordered by dependency (no circular deps)
- Check that no task violates an existing decision in `_memory/decisions.json`

## Step 4b: Consult Codex on the Sprint Plan

**Before presenting to Aryan, get Codex's take on the sprint plan.**

```bash
codex --exec 'You are reviewing a sprint plan for a Python data pipeline product (B2B content strategy engine with 8-step gap analysis pipeline, research agents, Reddit monitor).

SPRINT GOAL: {goal}
CONSTRAINTS: {from context.json}

PROPOSED TASKS:
{task list with descriptions}

Review this sprint plan and tell me:
1. MISSING TASKS — Is there anything we should do first that isn't listed? Any prerequisite work?
2. TASK ORDERING — Are dependencies correct? Would a different order be more efficient?
3. SCOPE RISK — Is this too much for one sprint? Which tasks could be deferred if needed?
4. BLIND SPOTS — Are there downstream effects or integration concerns we haven't considered?
5. TEST STRATEGY — Is the testing approach adequate for these changes?

Be specific and actionable.'
```
**NOTE: Always use model 'gpt-5.3-codex' for codex with 'high' reasoning_effort.**
**After Codex responds:**
- If Codex identifies missing prerequisite tasks → add them or note why they're not needed
- If Codex flags scope risk → mark tasks as "stretch" or defer to next sprint
- If Codex suggests reordering → evaluate and adjust if it makes sense
- Add a `## Codex Review Notes` section at the bottom of the PRD documenting what Codex said and what was incorporated vs. rejected

## Step 5: Get Approval
Present the PRD to Aryan. Wait for approval before writing it to disk.

## Step 6: Update Memory
After approval:
- Update `_memory/context.json` with new sprint info
- Update `_memory/progress.json` with new pending tasks