# Skill: Codex Integration

> Codex is Claude Code's second opinion. Use it to catch blind spots in plans and bugs in code.
Always use codex model = gpt-5.3-codex with 'high' reasoning effort when consulting codex.
---

## When to Consult Codex

### ALWAYS consult at Planning Stage (Step 3b in /dev)

Before presenting any implementation plan to Aryan, run it through Codex when the task involves:

- **Changing Pydantic models** — field additions, type changes, removed fields
- **Modifying pipeline data flow** — step inputs/outputs, artifact schemas
- **Adding new API integrations** — new SDKs, new endpoints
- **Changing LLM prompts** — s2 query gen, s8 report gen, Reddit HIL, research agents
- **Refactoring shared code** — anything in `core/shared_tools/`, `core/config/`

### ALWAYS consult at Review Stage (after implementation)

After completing any task, before presenting to Aryan.

### OPTIONAL consult for

- Pure test additions (low risk)
- Documentation-only changes
- Log format changes

---

## Prompt Templates

### Planning Review

```bash
codex --exec 'You are reviewing an implementation plan for a Python data pipeline (8-step gap analysis for B2B content strategy).

PROJECT CONTEXT:
- Python 3.12, asyncio, Pydantic v2, raw SDK clients (no LangChain)
- Pipeline: s1 (crawl+embed) → s2 (query gen) → s3 (search 4 AI platforms) → s4 (enrich citations) → s5 (embed) → s6 (analyze) → s7 (visualize) → s8 (report)
- Each step produces JSON artifacts consumed by the next step
- Backward compatibility with existing serialized artifacts is CRITICAL
- Models are in core/models/gap_analysis.py
- All new Pydantic fields MUST have defaults

TASK: {task_name}
FILES TO CHANGE: {file_list}

MY PLAN:
{drafted_plan}

Review and tell me:
1. MISSED EDGE CASES — What could break that I haven'\''t accounted for?
2. BLIND SPOTS — Downstream effects on other pipeline steps?
3. ALTERNATIVE APPROACHES — Simpler or more robust way to achieve the same goal?
4. BACKWARD COMPAT — Will this break deserialization of existing JSON artifacts in artifacts/gap_analysis/ramp/?
5. TEST GAPS — What test cases am I missing?

Be specific. Reference file names and function names.'
```

### Code Review

```bash
codex --exec 'Review this code for a Python data pipeline.

PROJECT CONTEXT:
- Python 3.12, asyncio, Pydantic v2, raw SDK clients
- 8-step gap analysis pipeline with JSON artifacts between steps
- Backward compatibility is critical — existing artifacts must still load
- All I/O functions are async via asyncio.to_thread()

FILES CHANGED:
{file_list_with_diffs}

Check for:
1. BUGS — Logic errors, off-by-one, None handling
2. EDGE CASES — Empty lists, missing keys, None fields
3. BACKWARD COMPATIBILITY — Will existing JSON artifacts still deserialize?
4. PYDANTIC V2 ISSUES — model_dump(mode="json") vs model_dump(), Field defaults, HttpUrl serialization
5. ASYNC CORRECTNESS — Proper await, no blocking in async context, semaphore usage
6. TYPE SAFETY — Missing type hints, incorrect types, Optional handling

Be specific. Quote the problematic code and explain the fix.'
```

### Architecture Decision Review

```bash
codex --exec 'I need to make an architectural decision for a Python data pipeline.

CONTEXT: {brief project context}

DECISION: {what needs to be decided}
OPTION A: {description}
OPTION B: {description}
OPTION C: {description if applicable}

For each option, evaluate:
1. Complexity of implementation
2. Risk of breaking existing functionality
3. Long-term maintainability
4. Impact on pipeline performance
5. Reversibility

Recommend one option with clear reasoning.'
```

---

## How to Use Codex Output

### Incorporating Feedback

After Codex responds, categorize each finding:

1. **INCORPORATE** — Codex caught something real. Add it to the plan/fix it in code.
2. **REJECT WITH REASON** — Codex suggested something that doesn't apply. Document why.
3. **DEFER** — Valid point but out of scope for this task. Log as tech debt.

### Presenting to Aryan

Always include a `CODEX REVIEW` section:

```
CODEX REVIEW:
- Incorporated: [what Codex caught that was added to the plan]
- Rejected: [what was suggested but not adopted, and why]
- Deferred: [valid points logged for later]
- No issues: [if Codex found nothing]
```

---

## Handling Disagreements

When Codex and Claude disagree on approach:

1. **Document both positions clearly:**
   ```
   DISAGREEMENT:
   Claude's position: [approach + reasoning]
   Codex's position: [approach + reasoning]
   Key tradeoff: [what each approach optimizes for]
   ```

2. **Present to Aryan with tradeoffs** — don't pick a winner silently

3. **Let Aryan decide** — wait for explicit approval

4. **Log the decision:**
   ```json
   {
     "id": "D{N}",
     "task": "T-v3-X: {task name}",
     "approach": "{chosen approach}",
     "rationale": "Aryan chose X because... Codex recommended Y because... Claude recommended Z because...",
     "alternatives_rejected": ["Codex: {approach}", "Claude: {approach}"],
     "outcome": "proceeding with {chosen}",
     "approved_by": "Aryan"
   }
   ```

---

## Timeout and Error Handling

### If Codex times out (120s):
1. Log the timeout: "Codex timed out on {task} planning review"
2. **Proceed without Codex** — don't block the workflow
3. Note in the plan: "CODEX: timed out — reviewed by Claude only"
4. Consider running Codex review at the /review stage instead

### If Codex returns an error:
1. Log the error message
2. Retry once with a shorter prompt
3. If still failing, proceed without and note it

### If Codex gives vague/unhelpful feedback:
1. Don't pad the report with generic advice
2. Report: "CODEX: no actionable findings"
3. Move on

---

## What Codex Is NOT For

- **Not a replacement for Aryan's approval** — Codex reviews, Aryan decides
- **Not for runtime decisions** — don't call Codex inside pipeline code
- **Not for prompt writing** — Codex reviews prompts, doesn't write them
- **Not infallible** — Codex can miss things or suggest wrong things. Use judgment.
