#!/bin/bash
# scripts/codex/architecture.sh — Evaluate an architecture decision through Codex
# Usage: bash scripts/codex/architecture.sh "$DECISION"
# Called by: /dev when DECISION NEEDED involves architecture choices

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/context.sh"

DECISION="${1:?Usage: architecture.sh \"\$DECISION\"}"

PROMPT="You are evaluating an architectural decision for the content-strategy-engine project.

${PROJECT_CONTEXT}

DECISION TO EVALUATE:
${DECISION}

Evaluate each option on these dimensions (score 1-5):
1. COMPLEXITY — How much code/config does this add?
2. RISK — What could go wrong? How bad is the failure mode?
3. MAINTAINABILITY — How easy is this to debug, extend, and modify later?
4. PERFORMANCE — Any latency, memory, or cost implications?
5. REVERSIBILITY — How hard is it to undo this decision if it's wrong?

Then provide:
- RECOMMENDED OPTION with reasoning
- MIGRATION PATH if the recommendation is chosen
- WARNING FLAGS to watch for during implementation"

run_codex "$PROMPT"
