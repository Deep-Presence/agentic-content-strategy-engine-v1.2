Read all memory files and output a concise project status dashboard.

Read:
- `_memory/progress.json`
- `_memory/failures.json`
- `_memory/decisions.json`
- `_memory/context.json`

Output format:
```
═══════════════════════════════════════════
  DEEP PRESENCE — STATUS
═══════════════════════════════════════════
  Sprint: vN | Goal: [sprint goal]
  Progress: X/Y tasks complete
───────────────────────────────────────────
  ✅ Completed (this sprint): [count]
     - [most recent 3 tasks]
  🔧 In Progress: [count]
     - [task] — [status/blocker]
  📋 Pending: [count]
     - [next 3 tasks by priority]
───────────────────────────────────────────
  ⚠️  Recent Failures: [count in last 7 days]
     - [most recent failure + lesson]
  📌 Decisions Pending: [any awaiting approval]
  💰 Constraints: [active constraints from context.json]
═══════════════════════════════════════════
```

If $ARGUMENTS is "verbose", include full task lists and all recent failures.
