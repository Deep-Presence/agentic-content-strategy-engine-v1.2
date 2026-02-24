#!/bin/bash
# scripts/codex/sprint-review.sh — Run sprint task list through Codex
# Usage: bash scripts/codex/sprint-review.sh "$TASK_LIST"
# Called by: /prd command (step 4b)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/context.sh"

TASK_LIST="${1:?Usage: sprint-review.sh \"\$TASK_LIST\"}"

PROMPT="You are reviewing a sprint plan (PRD with task breakdown) for the content-strategy-engine project.

${PROJECT_CONTEXT}

SPRINT TASK LIST TO REVIEW:
${TASK_LIST}

Please evaluate:
1. MISSING PREREQUISITES — Are there tasks that should come before others? Hidden dependencies?
2. TASK ORDERING — Is the sequence optimal? Can anything be parallelized?
3. SCOPE RISK — Is this sprint overloaded? Which tasks are highest risk?
4. BLIND SPOTS — Missing error handling tasks? Missing test tasks? Missing docs updates?
5. BACKWARD COMPATIBILITY — Do any tasks risk breaking existing pipeline behavior or artifacts?

For each concern, suggest a concrete fix (reorder, add task, split task, defer task)."

run_codex "$PROMPT"
