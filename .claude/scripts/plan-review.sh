#!/bin/bash
# scripts/codex/plan-review.sh — Run implementation plan through Codex
# Usage: bash scripts/codex/plan-review.sh "$PLAN"
# Called by: /dev command (step 3b)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/context.sh"

PLAN="${1:?Usage: plan-review.sh \"\$PLAN\"}"

PROMPT="You are reviewing an implementation plan for the content-strategy-engine project.

${PROJECT_CONTEXT}

IMPLEMENTATION PLAN TO REVIEW:
${PLAN}

Please identify:
1. EDGE CASES MISSED — What scenarios could break this plan?
2. BLIND SPOTS — What am I not seeing? Dependencies, ordering issues, race conditions?
3. BETTER ALTERNATIVES — Is there a simpler/safer approach I haven't considered?
4. BACKWARD COMPATIBILITY — Will this break existing JSON artifacts or pipeline skip behavior?
5. TEST GAPS — What tests should be written that aren't mentioned?

For each issue found, rate severity: HIGH / MEDIUM / LOW
Format as a numbered list grouped by category."

run_codex "$PROMPT"
