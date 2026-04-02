# Fix — Content Planner: Table Overflow + Drawer Revert

> **Read CLAUDE.md and brand-system.md first.** Three targeted fixes.

---

## Fix 1: Table — Stop Content Overflow

The table columns are overflowing. Titles are too long, Intent + Format text is wrapping, competing domain is cut off.

**Truncate the title to one line with ellipsis:**
```css
.title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
```

**Merge Intent + Format into one column** — they're taking too much space separately. Combine as: `Commercial · Comparison` in one cell, 12px, var(--text-secondary).

**Tighten the grid** — reduce total columns from 10 to 9:
```css
grid-template-columns: 36px 32px 1fr 88px 56px 100px 56px 72px 56px;
/* checkbox, rank, title, source, stage, intent·format, est.cit, competing, score */
```

**Competing column:** favicon (14px) + domain truncated with ellipsis. Max 72px. "New territory" text in green, 10px.

**Ensure the entire table stays within the page's 24px padding** — no horizontal scroll, no overflow. If needed, reduce font sizes in the table body to 13px for titles and 11px for metadata.

---

## Fix 2: Page Padding

Content is flowing outside container bounds. Fix:

```css
/* Page wrapper */
.page { padding: 0 24px; overflow-x: hidden; }

/* Table container */
.table { width: 100%; overflow: hidden; }

/* Filter bar */
.filters { width: 100%; flex-wrap: wrap; }
```

Make sure NOTHING extends beyond the content area. Add `overflow: hidden` on the main content wrapper.

---

## Fix 3: Drawer — Revert to Card-Based Design

The current drawer is too crowded with the editorial layout. **Revert to the card-based design from the previous version** but make it cleaner:

**Metrics section:** Two cards side by side with `1px solid var(--border)`, 14px padding. Estimated Citations left, Citation Opportunity right. Values at 28px JetBrains Mono. Clean, bordered, readable.

**Why We Recommend:** Three cards in a row with `border-top: 2px solid var(--amber)`, `1px solid var(--border)` on other sides, `background: var(--surface)`, 12px padding. Title at 13px font-weight 600. Text at 12px. These cards worked well in v5 — bring them back.

**Who Currently Owns This Space:** Each competitor in a card with `1px solid var(--border)`, 10px padding. Favicon + title + URL + word count + FAQ/Tables status. Same as v5 but with slightly less padding.

**Persona Affinity:** 2×2 grid of cards. Each card: `1px solid var(--border)`, percentage at 15px JetBrains Mono, full persona name at 12px. Primary card gets accent border and accent subtle background. Same as v5.

**Queries:** Table with 1px borders. Query text, fanouts count, intent pill. Same as current — this section is fine.

**Activity log:** Keep as-is — the timeline format works.

**Actions:** "Approve & Send to Studio" (green) + "Reject" (red outline) at the bottom. Keep as-is.

**Key difference from current:** Add `16px` gap between each section. Add `border-top: 1px solid var(--border)` as separator between sections. Each section header: 11px uppercase var(--text-secondary) with 12px margin-bottom. This creates clear visual separation without crowding.

**Drawer internal padding:** 20px all sides. Consistent throughout.

---

## Verification

1. Table fits within page bounds — no horizontal overflow
2. All titles truncated with ellipsis on one line
3. Intent + Format merged into one column
4. Drawer sections use bordered cards — not bare editorial layout
5. 16px gap between drawer sections
6. Drawer doesn't feel crowded — clear visual breathing room
7. `npm run build` succeeds
