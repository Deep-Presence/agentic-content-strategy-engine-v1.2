#!/bin/bash
# scripts/codex/code-review.sh — Run code diff through Codex
# Usage: bash scripts/codex/code-review.sh "$DIFF"
# Called by: /dev (post-implementation), /review command

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/context.sh"

DIFF="${1:?Usage: code-review.sh \"\$DIFF\"}"

PROMPT="You are reviewing a code change for the content-strategy-engine project.

${PROJECT_CONTEXT}

CODE DIFF TO REVIEW:
${DIFF}

Check for:
1. BUGS — Logic errors, off-by-one, None handling, type mismatches
2. EDGE CASES — Empty lists, missing keys, None values, network timeouts
3. BACKWARD COMPATIBILITY — New Pydantic fields without defaults? model_dump(mode='json') used? Existing artifact loading still works?
4. PYDANTIC V2 CORRECTNESS — Field(default_factory=list) for mutables? HttpUrl serialization? Optional vs default semantics?
5. ASYNC CORRECTNESS — asyncio.to_thread for sync calls? Semaphore usage? No blocking in event loop?
6. TYPE SAFETY — All function signatures typed? Return types specified? Generic types correct?

For each issue found, provide:
- File and approximate location
- Severity: HIGH / MEDIUM / LOW
- Suggested fix"

run_codex "$PROMPT"
