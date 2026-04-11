#!/usr/bin/env bash
# dev.sh — Start backend + frontend with auto-logging
# Usage: ./scripts/dev.sh
# Logs go to: backend-log.txt, front-log.txt (project root)
# Claude Code can read these files anytime.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

BACKEND_LOG="$ROOT/backend-log.txt"
FRONTEND_LOG="$ROOT/front-log.txt"

# Truncate old logs
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

echo "=== Starting backend (port 8000) — logging to backend-log.txt ==="
cd "$ROOT"
python scripts/run_server.py 2>&1 | tee "$BACKEND_LOG" &
BACKEND_PID=$!

echo "=== Starting frontend (port 3001) — logging to front-log.txt ==="
cd "$ROOT/frontend"
npm run dev 2>&1 | tee "$FRONTEND_LOG" &
FRONTEND_PID=$!

echo ""
echo "Both servers running. Ctrl+C to stop both."
echo "Logs: $BACKEND_LOG | $FRONTEND_LOG"
wait
