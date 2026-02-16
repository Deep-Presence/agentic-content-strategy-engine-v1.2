#!/usr/bin/env bash
# Fix Cursor MCP tool "Blocked by permissions configuration"
# Run with: ./scripts/fix_cursor_mcp_permissions.sh
# Prerequisite: Close Cursor completely before running

set -euo pipefail

ROOT="${HOME}/Library/Application Support/Cursor"
STAMP=$(date +%Y%m%d-%H%M%S)
KEY='src.vs.platform.reactivestorage.browser.reactivestorageServiceImpl.persistentStorage.applicationUser'

if [[ ! -d "$ROOT" ]]; then
  echo "Cursor config not found at: $ROOT"
  echo "On Linux, use: ROOT=\"\${HOME}/.config/Cursor\""
  exit 1
fi

echo "Backing up and fixing Cursor MCP permissions..."
echo ""

find "$ROOT/User" -type f -name "state.vscdb" 2>/dev/null | while IFS= read -r DB; do
  echo "Processing: $DB"
  cp -v "$DB" "${DB}.bak.${STAMP}"

  sqlite3 "$DB" <<SQL
PRAGMA busy_timeout=5000;
BEGIN;
UPDATE ItemTable SET value=json_set(value,
  '$.shouldAutoContinueToolCall', 1,
  '$.yoloMcpToolsDisabled', 0,
  '$.isAutoApplyEnabled', 1
) WHERE key='$KEY';

UPDATE ItemTable SET value=json_set(value,
  '$.composerState.shouldAutoContinueToolCall', 1,
  '$.composerState.yoloMcpToolsDisabled', 0,
  '$.composerState.modes4[0].autoRun', 1,
  '$.composerState.modes4[0].fullAutoRun', 1,
  '$.composerState.useYoloMode', 0
) WHERE key='$KEY';

UPDATE ItemTable SET value=REPLACE(value,'"mcpEnabled": false','"mcpEnabled": true')
WHERE key='$KEY' AND value LIKE '%"mcpEnabled": false%';
COMMIT;
SQL

  echo "  Done."
  echo ""
done

echo "Fix complete. Restart Cursor and test the Langfuse docs tool."
