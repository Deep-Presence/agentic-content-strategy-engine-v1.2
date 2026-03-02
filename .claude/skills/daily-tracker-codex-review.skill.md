# Skill: Codex Review Protocol — Daily Tracker Module

**Applies to**: All implementation teammates (prompt-library, platform-runner, analytics, integration)

## Why

Every implementation teammate runs a mandatory Codex code review before committing. This catches security flaws, broken contracts, race conditions, and edge cases that unit tests miss. This pattern is established in our codebase — see decisions D-AUTH-1, D-GUARD-1, D-DB-1, D-TASK-1 for past Codex reviews that caught critical issues.

## Configuration

| Setting | Value |
|---------|-------|
| **Model** | `gpt-5.3-codex` |
| **Reasoning effort** | `high` |
| **Scope** | All files the teammate created + relevant protocols/patterns |

## Workflow

### Step 1: Ensure all tests pass first

```bash
python -m pytest tests/daily_tracker/<your_test_files> -v
```

Do NOT run Codex review if tests are failing. Fix tests first.

### Step 2: Run Codex review

```bash
codex --model gpt-5.3-codex --reasoning-effort high \
  -p "You are a senior code reviewer. Critically review ALL of the following files for:
      1. CRITICAL issues: security flaws, data loss risks, race conditions, broken contracts
      2. WARNING issues: missing edge cases, incorrect error handling, performance problems, API misuse
      3. INFO issues: style inconsistencies, naming, documentation gaps

      Files to review:
      <LIST YOUR FILES HERE>

      Also review against:
      - core/daily_tracker/protocols.py (does implementation satisfy the Protocol?)
      <ADD RELEVANT REFERENCE FILES>

      For each finding, state severity (CRITICAL/WARNING/INFO), file:line, and a concrete fix.
      Be ruthless. This code goes to production."
```

### Step 3: Triage findings

| Severity | Action |
|----------|--------|
| **CRITICAL** | Fix ALL. No exceptions. These are security flaws, data loss, or broken contracts. |
| **WARNING** | Fix all that are relevant. If you reject one, add a comment explaining why. |
| **INFO** | Fix easy ones. Defer the rest. |

### Step 4: Re-run tests after fixes

```bash
python -m pytest tests/daily_tracker/<your_test_files> -v
```

### Step 5: Commit with review summary

```bash
git add .
git commit -m "feat(daily-tracker): <teammate-name> — <description>

Codex gpt-5.3-codex review (high reasoning):
- X CRITICAL, Y WARNING, Z INFO findings
- All CRITICALs incorporated
- <1-line summary of most important fix>"
```

### Step 6: Message the lead

Tell the lead you're done, including the Codex review summary (finding counts + key fixes).

## Per-Teammate Review Focus Areas

### prompt-library
- Protocol compliance with `PromptLibraryServiceProtocol`
- Repository pattern correctness (flush-only contract)
- Deduplication correctness
- Import from gap analysis edge cases

### platform-runner
- **ZERO code duplication** with gap analysis engines (adapter only)
- Async concurrency control (semaphore pattern)
- Error handling (engine failures must not crash the run)
- Mention detection regex correctness and case sensitivity

### analytics
- Mathematical correctness (rates 0-1, SOV sums ~1.0, no division by zero)
- Strategy pattern compliance (new calculators without modifying AnalyticsService)
- Pure computation guarantee (no I/O, no API calls)
- Edge cases: empty data, single data point trends

### integration
- Mediator pattern (orchestrator coordinates, modules don't talk directly)
- Background task lifecycle (trigger returns immediately, errors captured)
- Auth/tenant isolation on all endpoints
- DI wiring correctness (no circular imports)
- Run status transitions (no stuck states)
- Cross-module integration correctness
