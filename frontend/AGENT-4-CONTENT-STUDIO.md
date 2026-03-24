# Agent 4 — Content Studio

> **Read CLAUDE.md first, then this file.** Runs parallel after Agent 1. Most complex agent scope.

## Prerequisites Check

```bash
ls src/components/ui/index.ts && ls src/types/index.ts
ls node_modules/@dnd-kit/core/package.json    # dnd-kit installed
ls data/artifacts/content/carta/content/brief-001/formatted.md  # Real content exists
npm run dev
```

## Files You Own

```
src/app/(dashboard)/content/page.tsx
src/app/(dashboard)/content/_components/
```

## Data Sources — Real Content Pipeline

| Data | Source | Notes |
|------|--------|-------|
| Brief 001 pipeline | `data/artifacts/content/carta/content/brief-001/` | outline→draft→enriched→final→formatted (all .md) |
| Brief 002 pipeline | `data/artifacts/content/carta/content/brief-002/` | Same pipeline stages |
| Brief metadata | `data/artifacts/content/carta/briefs.json` | Import directly |
| Eval history | `data/artifacts/content/carta/content/brief-*/eval_history.json` | Quality tracking |

---

## Step 1: Page Layout Shell

```
┌──────────────┬──────────────────────────────────┬─────────────┐
│ Cycles       │                                  │ Agent       │
│ Sidebar      │    Board View / Content View      │ Activity    │
│ (220px)      │    (fills remaining)               │ (280px,     │
│              │                                  │ collapsible) │
└──────────────┴──────────────────────────────────┴─────────────┘
```

Use CSS grid or flex for this 3-column layout. Agent activity sidebar collapses to just an icon toggle.

### ✅ Verify Before Proceeding

Visit `/content`. You should see the 3-column skeleton: left sidebar, main area, right panel. If layout breaks, check flex/grid setup before adding content.

---

## Step 2: Left Sidebar — Cycles & History

**Cycles tree:** Expandable weeks with content items.
```tsx
<div className="border-r border-border w-[220px] overflow-y-auto">
  <div className="p-3">
    <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary">
      CURRENT CYCLE
    </span>
    <div className="mt-2 space-y-1">
      <div className="flex items-center gap-2 p-[5px_8px] rounded-sm hover:bg-surface cursor-pointer">
        <StatusDot status="review" />
        <span className="text-[12px] text-text-primary truncate">International Equity Grants Guide</span>
      </div>
      {/* more items... */}
    </div>
  </div>
</div>
```

**History section:** Published content with citations earned, CPS data.

### ✅ Verify: Cycles sidebar renders with items. Clicking an item should eventually open Content View (wire this up in Step 4).

---

## Step 3: Board View — 5-Column Kanban

Use `@dnd-kit/core` + `@dnd-kit/sortable`. 5 columns: Triage → Brief → Generating → Review → Approved.

**Card component:**
```tsx
function ContentCard({ brief }: { brief: ContentBrief }) {
  return (
    <div className="bg-surface border border-border rounded-sm p-[10px] cursor-grab hover:border-border-strong transition-[border-color] duration-150">
      <h4 className="text-[13px] font-semibold text-text-primary leading-tight mb-1 line-clamp-2">
        {brief.title}
      </h4>
      <div className="flex items-center gap-1 mb-2">
        {brief.personas.map(p => <StatusDot key={p} status="active" />)}
      </div>
      <div className="flex justify-between items-center">
        <Badge variant="info">{brief.targetCluster}</Badge>
        <span className="text-[10px] text-text-tertiary">3d ago</span>
      </div>
    </div>
  );
}
```

**Mock data:** Create 8-10 items across all stages. Use real titles from gap report:
- Triage: "Secrets & Environment Variables in Prompt-to-App Tools", "SOC 2 + GDPR for AI Development Platforms", "RBAC in AI-Generated Apps"
- Brief: "Audit Logs & Change History for AI App Builders" (review ready), "Bolt.new Alternatives 2026" (brief generating)
- Generating: "International Equity Grants: Compliance Guide" (from real brief-001)
- Review: "Pro-Rata Rights in Venture Financing" (from real brief-002)
- Approved: 2 items with published dates

### ✅ Verify Before Proceeding

Board shows 5 columns with cards. Drag a card from Triage to Brief — it should move. If drag doesn't work, check `DndContext` and `SortableContext` setup. Each card should show title, persona dots, cluster badge.

---

## Step 4: Content View — Editor + Scoring

Full-screen overlay/panel. Opens from any card click.

**Left (~65%) — Editor:**
- Plain Google Doc-style surface. Use `contentEditable` div or TipTap.
- **No section blocks.** Continuous text flow.
- On text selection → floating toolbar:
  - Row 1 (AI): Regenerate | Rewrite | Shorten | Expand | Change Tone
  - Row 2 (Format): Bold | Italic | Link | H2 | H3 | Quote
  - Toolbar: `bg-surface-raised border border-border shadow-float rounded-md p-1`

**Example: Floating Toolbar**
```tsx
{showToolbar && (
  <div
    className="absolute bg-surface-raised border border-border rounded-md shadow-float p-1 flex gap-1 z-50"
    style={{ top: toolbarPosition.y, left: toolbarPosition.x }}
  >
    <button className="h-[26px] px-2 text-[11px] text-text-secondary hover:bg-surface rounded-sm">
      Regenerate
    </button>
    <button className="h-[26px] px-2 text-[11px] text-text-secondary hover:bg-surface rounded-sm">
      Rewrite
    </button>
    {/* ... more actions */}
  </div>
)}
```

AI actions can be no-op with toast ("Coming soon — AI regeneration") for now.

**Load real content:** For Review-stage items, load `data/artifacts/content/carta/content/brief-001/formatted.md` and `brief-002/formatted.md` as the editor content.

**Right (~35%) — Scoring Panel:**
- CPS per platform (5 bars): ChatGPT, Claude, Perplexity, Google AI Overview, Gemini
- Structural compliance: word count current/target, headers, FAQ, citation density, reading level
- Voice compliance: 0-100%
- Interlink suggestions: checkboxes
- "View in Embedding Space" button
- **Live update:** On text change (debounced 500ms), recalculate word count, header count, etc.

**Bottom action bar:** Approve | Send Back with Feedback | Re-run All | Download | Copy | Publish

### ✅ Verify Before Proceeding

Click a Review card. Content View opens with real markdown rendered in editor. Select text — toolbar appears. Right panel shows CPS scores for all 5 platforms. Edit text — word count updates. Bottom bar shows action buttons.

---

## Step 5: Agent Activity Sidebar

Right edge, 280px, collapsible via icon toggle. Feed of timestamped agent actions:
```
Writer Agent — Started generation for "International Equity Grants Guide" — 14:23
Interlink Agent — Found 4 internal link opportunities — 14:25
Strategy Agent — Adjusted heading structure — 14:26
Image Agent — Generated hero image (DALL-E 3) — 14:28
```
Filterable by agent type.

### ✅ Verify: Toggle shows/hides sidebar. Feed scrolls. Filter works.

---

## Troubleshooting

### @dnd-kit Cards Don't Drag
**Symptom:** Cards are clickable but not draggable.
**Fix:** Ensure cards are wrapped in `useSortable()` hook and have `{...attributes} {...listeners}` spread on the drag handle element. Check `DndContext` wraps the entire board.

### @dnd-kit Drop Not Registering
**Symptom:** Card lifts but drops back to original position.
**Fix:** Implement `onDragEnd` handler that updates state by moving the item between column arrays. The handler must call `setItems(newState)` — if you forget to update state, nothing persists.

### Text Selection Toolbar Position Wrong
**Symptom:** Toolbar appears at wrong coordinates or off-screen.
**Fix:** Use `window.getSelection().getRangeAt(0).getBoundingClientRect()` for position. Account for scroll offset: add `window.scrollY` to top, `window.scrollX` to left.

### contentEditable HTML Injection
**Symptom:** Pasting text includes unwanted HTML formatting.
**Fix:** On paste event, use `e.clipboardData.getData('text/plain')` and `document.execCommand('insertText', false, text)` to paste plain text only.

### Real Markdown Renders as Raw Text
**Symptom:** Content from brief-001 shows markdown syntax instead of formatted text.
**Fix:** If using contentEditable, you need to convert markdown to HTML before setting innerHTML. Use a simple markdown-to-HTML converter or render with `react-markdown` in read mode, `contentEditable` in edit mode.

### CPS Scores Don't Update
**Symptom:** Right panel shows static scores that never change.
**Fix:** Implement a debounced `useEffect` watching editor content. On change, recalculate: `wordCount = text.split(/\s+/).length`, `headerCount = (text.match(/^#{2,3}\s/gm) || []).length`, etc.

---

## Completion Criteria

- [ ] 5-column Kanban renders with cards in each column
- [ ] Drag-and-drop moves cards between columns
- [ ] Content View opens from card click
- [ ] Real markdown from brief-001/brief-002 loads in editor
- [ ] Text selection shows floating toolbar with AI + format actions
- [ ] CPS shows all 5 platforms (ChatGPT, Claude, Perplexity, Google AI Overview, Gemini)
- [ ] Structural scores update on text edit (debounced)
- [ ] HITL checkpoints: Approve/Feedback/Reject at Brief and Review stages
- [ ] Agent activity sidebar toggles and shows feed
- [ ] Cycles sidebar shows tree with status dots
- [ ] Bottom action bar with all buttons
- [ ] `npx tsc --noEmit` — 0 errors
