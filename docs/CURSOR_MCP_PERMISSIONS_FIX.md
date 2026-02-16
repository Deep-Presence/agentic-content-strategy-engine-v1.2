# Fix: MCP Tool "Blocked by Permissions Configuration"

When you see:
```
Permission denied: MCP tool execution blocked: user-langfuse-docs-searchLangfuseDocs - Blocked by permissions configuration
```

The Langfuse docs MCP tool is being blocked. Here's how to fix it.

---

## Option 1: Cursor Settings (Try First)

1. **Open Cursor Settings**
   - `Cmd + ,` (Mac) or `Ctrl + ,` (Windows/Linux)
   - Or: **Cursor** → **Settings** → **Cursor Settings**

2. **Go to Features**
   - In the left sidebar, click **Features**
   - Look for **"Run Everything"** or **"Auto-run mode"** and enable it
   - Or look for **MCP** / **Tools** and ensure MCP tools are allowed

3. **When the tool prompts you**
   - If you see a prompt like "Run" / "Skip" / "Add to allowlist"
   - Click **"Add to allowlist"** so future runs don't require approval

---

## Option 2: Database Fix (If UI Doesn't Work)

Cursor stores MCP permissions in SQLite. The UI can be overridden by these values.

### Prerequisites
- **Close Cursor completely** (quit the app, not just minimize)
- Install SQLite: `brew install sqlite3` (macOS)

### Run the fix script

From this project root:

```bash
./scripts/fix_cursor_mcp_permissions.sh
```

Or manually:

```bash
# 1. Backup
cp "$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb" \
   "$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb.bak.$(date +%Y%m%d-%H%M%S)"

# 2. Apply fix (macOS)
# The script updates composerState to allow MCP tools to run
```

### Manual database edit (advanced)

1. Install [DB Browser for SQLite](https://sqlitebrowser.org/) or use `sqlite3` CLI
2. Open: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`
3. Find the row where `key` contains `reactivestorage`
4. Edit the `value` JSON to include:
   ```json
   {
     "composerState": {
       "shouldAutoContinueToolCall": 1,
       "yoloMcpToolsDisabled": 0,
       "modes4": [{ "fullAutoRun": 1 }],
       "useYoloMode": 0
     }
   }
   ```

---

## Option 3: Verify MCP Server is Enabled

1. Open **Cursor Settings** → **Features** → **MCP**
2. Ensure **langfuse-docs** (or `user-langfuse-docs`) is listed and **enabled**
3. If it's disabled, enable it and restart Cursor

---

## After Applying

1. **Restart Cursor** completely
2. Trigger the Langfuse docs tool again (e.g. ask a Langfuse-related question)
3. If it still blocks, try Option 2 (database fix)

---

## References

- [Cursor MCP Docs](https://cursor.com/docs/cli/mcp)
- [Fix MCP Allowlist Issues (Dre Dyson)](https://dredyson.com/fix-mcp-allowlist-issues-in-cursor-ide-a-complete-beginners-step-by-step-guide-to-avoid-costly-configuration-mistakes/)
- [Cursor Forum: MCP Allowlist Bug](https://forum.cursor.com/t/mcp-allowlist-doesnt-work-also-cant-be-edited/135594)
