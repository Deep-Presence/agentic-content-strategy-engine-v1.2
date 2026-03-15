#!/usr/bin/env bash
# Kill all processes using port 8000
PORT=${1:-8000}
PIDS=$(lsof -ti :"$PORT" 2>/dev/null)

if [ -z "$PIDS" ]; then
  echo "No processes found on port $PORT"
  exit 0
fi

echo "Killing processes on port $PORT: $PIDS"
echo "$PIDS" | xargs kill -9 2>/dev/null
sleep 0.5

# Verify
REMAINING=$(lsof -ti :"$PORT" 2>/dev/null)
if [ -z "$REMAINING" ]; then
  echo "Port $PORT is now free"
else
  echo "Warning: processes still on port $PORT: $REMAINING"
fi