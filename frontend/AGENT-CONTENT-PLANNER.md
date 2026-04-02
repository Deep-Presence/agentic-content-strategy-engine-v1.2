# Agent — Content Planner Page (Production)

> **Read CLAUDE.md and brand-system.md first, then this file.** This is a FULL REBUILD of the `/planner` page.

---

## Mission

Build the Content Planner page — the page where users **discover and select** content to produce. This page shows well-researched content recommendations ranked by citation potential. Users review, approve, or reject recommendations. Approved items flow to Content Studio. Rejected items go to a minimal rejected list.

The page has THREE content sources:
1. **Gap Analysis** — recommendations generated from the citation gap pipeline
2. **Strategic Initiatives** — user-defined content directions where AI researches the space and generates recommendations
3. **Custom Topics** — individual topics the user creates manually, enriched by AI with citation scoring

The page has TWO views:
1. **Priority Queue** (default) — flat ranked table of ALL recommendations across all clusters
2. **Cluster Explorer** — tree navigation: Cluster → Subcluster → Assignments

Plus a minimal **Rejected** tab showing passed-on topics.

---

## Files You Own

```
src/app/(dashboard)/planner/page.tsx
src/app/(dashboard)/planner/_components/
```

**DELETE** whatever currently exists at this route. Full rebuild. **Never touch** shared UI components, other pages, stores, or layout files.

---

## MANDATORY LAYOUT STANDARDS

### Density & Spacing

```
Page-level horizontal padding: max 24px — NO max-w-7xl or container wrappers
Section gaps: 16px
Card internal padding: 10px-12px
Table cell padding: 6px vertical, 8px horizontal
Table row height: 44px (allows two-line titles)
```

Replace `p-6`/`p-8`/`gap-6`/`gap-8` → `p-3`/`p-4`/`gap-3`/`gap-4`. Remove `max-w-7xl mx-auto`.

### Font Sizes (non-negotiable)

```
Page title: 20px, font-weight 600, Space Grotesk
Page subtitle: 11px, var(--text-secondary)
Table headers: 9px, uppercase, letter-spacing 0.05em, var(--text-secondary), font-weight 600
Table body text: 12px
Content ID: 10px, JetBrains Mono, var(--text-secondary)
Assignment title in table: 12px, font-weight 500
Assignment subtitle (cluster path): 10px, var(--text-secondary)
Score values: 11px, JetBrains Mono
Pill/badge text: 9px, uppercase, font-weight 600
Section headers in drawer: 10px, uppercase, letter-spacing 0.05em, font-weight 600
Drawer title: 16px, font-weight 600
Drawer body text: 11px
Filter labels: 10px, uppercase, var(--text-secondary)
```

### Global Filter Bar

Sits directly below page header. Full-width. Height 40px. No rounded corners. `border-bottom` only.

Filters (left-aligned): **Stage** (All / TOFU / MOFU / BOFU), **Persona** (All / Solo Founder / Product Manager / Agency Owner / Technical Engineer), **Source** (All / Gap Analysis / Strategic / Custom). Vertical dividers between each filter. "× Clear" appears when any filter is active.

View toggle (right-aligned): **Priority Queue** | **Cluster Explorer** | **Rejected (N)** — segmented button group. Active tab: accent background, white text.

---

## ANIMATIONS (Apply throughout)

Use Framer Motion if available in the project, otherwise CSS keyframes. All animations should be subtle and fast — 150-300ms. Nothing should feel sluggish.

```css
@keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
@keyframes slideRight { from { opacity: 0; transform: translateX(16px); } to { opacity: 1; transform: translateX(0); } }
@keyframes scaleIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes barGrow { from { width: 0; } }
```

Apply `fadeUp` with staggered delays (25-40ms per row) on table rows. `slideRight` on drawer open and cluster explorer right panel. `scaleIn` on modals. `fadeIn` on overlays. `barGrow` on score bars. All hover transitions: 150ms.

---

## PAGE HEADER

```
Content Planner
Well-researched content recommendations ranked by citation potential

[✦ Initiatives]  [+ Custom Topic]
```

Title: 20px font-weight 600. Subtitle: 11px var(--text-secondary). Two buttons right-aligned:
- "✦ Initiatives" — purple-tinted (`background: var(--purple-subtle)`, `color: var(--purple)`, `border: 1px solid var(--purple) at 30%`). Opens Strategic Initiatives sidebar.
- "+ Custom Topic" — transparent with border. Opens Custom Topic modal.

---

## CONTENT IDs

Every assignment has a unique ID in format `DP-XXX` (Deep Presence content ID). This ID:
- Shows in the table row (below the title, 10px JetBrains Mono, var(--text-secondary))
- Shows in the drawer header
- Shows in the cluster explorer rows
- Gets passed to Content Studio when approved
- Is part of the shareable link: `https://app.deeppresence.com/planner/DP-001`

---

## PRIORITY QUEUE VIEW (Default)

### Table Columns

| Column | Width | Content |
|--------|-------|---------|
| Checkbox | 28px | Select/deselect. Click header checkbox → select ALL (not just visible) |
| # | 28px | Rank number, JetBrains Mono 10px, var(--text-secondary) |
| Title | flex 1 | Title (12px font-weight 500) on line 1. Below: `DP-001 · Competitive Landscape → Pricing & Value` (10px var(--text-secondary)). Allow wrap to 2 lines, row height 44px |
| Source | 78px | Badge: "Gap Analysis" (teal), "Strategic" (purple), "Custom" (gray) |
| Stage | 48px | TOFU (teal) / MOFU (amber) / BOFU (green) pill |
| Intent | 52px | Informational / Commercial / Navigational / Transactional — 9px pill, subtle styling |
| Format | 48px | Guide / Comparison / Tutorial / Listicle / Case Study — 10px text |
| Est. Cit. | 56px | `~22` — JetBrains Mono 12px, accent color, font-weight 600. Sortable column |
| Competing | 68px | Favicon + domain of top competitor, or "New territory" in green if no competitors |
| Score | 56px | Mini bar (28px wide, 3px height) + score value (JetBrains Mono 11px). Sortable column |

### Sorting

Default: sort by Score descending. Clicking "Est. Cit." or "Score" headers toggles sort. Active sort column header is accent-colored with ↓ arrow.

### Row Interaction

- Hover: `var(--hover)` background, 150ms transition
- Click: opens detail drawer
- Selected (via checkbox): subtle accent background tint

### Bulk Actions Bar

When 1+ checkboxes are selected, a bar appears above the table (animated fadeUp):

```
[3 selected]  [✓ Approve & Send to Studio]  [✗ Reject]  [Cancel]
```

"Approve" button: green background, white text. On click: selected items removed from list, toast: "✓ 3 topics approved → Content Studio". "Reject": removes items, toast: "✗ 3 topics rejected".

### Footer

Below table: `{N} recommendations pending` — 11px var(--text-secondary).

### Mock Data — 10 Assignments

```typescript
interface Assignment {
  id: string;           // "DP-001"
  title: string;
  cluster: string;
  subcluster: string;
  stage: "TOFU" | "MOFU" | "BOFU";
  intent: "Informational" | "Commercial" | "Navigational" | "Transactional";
  format: "Guide" | "Comparison" | "Tutorial" | "Listicle" | "Case Study";
  source: "gap" | "strategic" | "custom";
  initiative?: string;  // name of strategic initiative, if source === "strategic"
  personaScores: { sf: number; pm: number; da: number; te: number }; // percentages 0-100
  persona: string;      // primary persona id ("sf", "pm", "da", "te")
  estCitations: number;
  citationOpp: number;  // 0-1
  priorityScore: number; // 0-1, composite score
  effort: "low" | "medium" | "high";
  estDays: number;
  competitors: Array<{
    domain: string;
    title: string;
    url: string;        // full path, no https://
    words: number;
    faq: boolean;
    tables: boolean;
    rank: number;
  }>;
  reasons: Array<{ title: string; text: string }>;  // exactly 3 reasons
  relatedQueries: Array<{
    query: string;
    fanouts: number;
    intent: "Informational" | "Commercial";
  }>;
  createdAt: string;    // "Mar 18, 2026"
  activityLog: Array<{ action: string; date: string; by: string }>;
}
```

Generate 10 assignments with realistic data across 5 clusters. Include:
- 4 from gap analysis
- 4 from strategic initiatives (2 from "Technical Engineer Expansion", 2 from "Enterprise Security Push")
- 1 custom topic
- 1 that is "new territory" (empty competitors array)

Ensure mock data covers:
- All 4 funnel stages
- All 4 intent types
- All 5 formats
- All 4 personas as primary
- Low/medium/high effort mix
- estCitations range: 7-22
- citationOpp range: 0.61-0.85
- priorityScore range: 0.55-0.85

**Reference the content-planner-v5.jsx prototype for exact data values** — use the same assignment titles, clusters, subclusters, and scores from that file. Do not invent new ones.

---

## CLUSTER EXPLORER VIEW

### Left Panel — Tree Navigation (230px width)

Clusters as collapsible sections. Click cluster name → expand/collapse with smooth height transition (250ms).

Each cluster row: chevron (rotates on expand, 200ms), cluster name (12px font-weight 600), assignment count (JetBrains Mono 10px, right-aligned).

Each subcluster row: indented 22px, name (11px), count (10px JetBrains Mono). Active subcluster: accent color, accent left border (2px), accent subtle background.

### Right Panel — Subcluster Detail

#### Header
```
SECURITY & COMPLIANCE          Sort: [Highest Score ▾]
Data Privacy & GDPR
```

Cluster name: 10px uppercase var(--text-secondary). Subcluster name: 16px font-weight 600. Sort dropdown (right-aligned): Highest Score / Most Citations / Opportunity.

#### Stats Row (2 cards)
```
CITATION OPPORTUNITY    TOTAL EST. CITATIONS
68%                     ~10
```

Two cards side by side. JetBrains Mono 20px values. 1px border, 10px padding.

#### Assignment List — LEAN ROWS

Each assignment as a compact row in a bordered container. Row height: ~44px (can expand for two-line titles).

```
DP-007  GDPR Compliance for No-Code AI Platforms    [STRATEGIC] [MOFU]  ~10  [✓] [✗]
```

Columns: ID (10px mono) | Title (12px, wraps to 2 lines) | Source + Stage badges | Est Citations (11px mono accent) | Approve/Reject mini buttons (✓ green, ✗ gray, 18×18px).

Hover: background change, 150ms. Click row (not buttons): opens detail drawer. Buttons are independent — approve/reject without opening drawer.

When a subcluster has 0 assignments: show "No recommendations for this subcluster" centered.

---

## DETAIL DRAWER (50% viewport width)

Slides from right. Backdrop: `rgba(0,0,0,0.2)`. Animation: slideRight 200ms.

### Drawer Layout (top to bottom)

#### 1. Header

```
DP-001  [GAP ANALYSIS]  [BOFU]  [COMPARISON]  [COMMERCIAL]  [MEDIUM EFFORT]     [🔗] [✕]
```

Content ID in mono. Source badge. Stage pill. Format pill. Intent pill. Effort pill. Share icon button (copies link, shows "✓ Copied" tooltip for 1.5s). Close button.

Below pills:
```
AI App Builder Pricing Comparison: Which Platform Offers the Best Value?
Competitive Landscape → Pricing & Value
```

Title: 16px font-weight 600. Path: 11px var(--text-secondary).

If from strategic initiative: show `[Initiative: Technical Engineer Expansion]` purple pill below path.

#### 2. Key Metrics (2 cards)

```
┌─────────────────────┬──────────────────────┐
│ ESTIMATED CITATIONS  │ CITATION OPPORTUNITY │
│ ~22                  │ 82%                  │
│ ▁▂▃▅▇ (mini bars)   │ whitespace score     │
└─────────────────────┴──────────────────────┘
```

Two cards side by side. `1px solid var(--border)`, 10px padding.

- Est. Citations: JetBrains Mono 24px font-weight 700, accent color. Below the number: a tiny 3-bar ascending graphic (three small rectangles — 4px, 7px, 11px height, 4px wide, 2px gap, accent color at varying opacity) suggesting "growing opportunity". NO text like "within 30 days."
- Citation Opportunity: JetBrains Mono 24px font-weight 700, accent color. Below: "whitespace score — higher = less competition" in 10px var(--text-secondary).

#### 3. Why We Recommend This (3 cards, horizontal)

```
┌────────────────┬────────────────┬────────────────┐
│ amber top      │ amber top      │ amber top      │
│ border         │ border         │ border         │
│                │                │                │
│ Bold Title     │ Bold Title     │ Bold Title     │
│ Supporting     │ Supporting     │ Supporting     │
│ text here      │ text here      │ text here      │
└────────────────┴────────────────┴────────────────┘
```

Three cards in a row (`grid-cols-3`, gap 6px). Each card: `border-top: 2px solid var(--amber)`, `1px solid var(--border)`, `background: var(--surface)`, 10px padding. Title: 11px font-weight 600. Text: 10px var(--text-secondary), line-height 1.5.

Each assignment has exactly 3 reasons. Reasons should be specific and evidence-based, not generic.

#### 4. Who Currently Owns This Space

**If competitors exist:** Show ranked list of competitor pages.

Each competitor: card with 1px border, 8px padding.
```
#1  [favicon] Bolt.new Pricing Breakdown          2,800 words  FAQ ✓  Tables ✓
              bolt.new/blog/pricing-breakdown ↗
```

Rank: 10px mono. Favicon: 16px. Title: 12px font-weight 500. URL: 10px accent color, clickable external link (↗ icon). Word count + structural indicators: 10px var(--text-secondary). FAQ/Tables: green ✓ if present, red ✗ if missing.

Show up to 3 competitors.

**If NO competitors (new territory):** Show a green-tinted card:
```
🏳 New Territory — No Competition
No authoritative content exists for this topic in AI engine citations.
First-mover opportunity with zero established competition.
```

Background: var(--green-subtle). Border: `1px solid var(--green) at 20%`. Title: 12px font-weight 600, green. Text: 11px var(--text-secondary).

#### 5. Persona Affinity

2×2 grid of persona cards. Each card:
```
┌──────────────────────────┐
│ 92%  Solo Founder    ═══ │
│      Primary target      │
└──────────────────────────┘
```

Percentage: JetBrains Mono 14px font-weight 600. Name: 11px font-weight 500. Mini progress bar (48px, 3px height) showing the percentage. Primary persona: accent border, accent subtle background, "Primary target" label in 9px accent.

#### 6. Queries This Content Would Answer

Expanded query list with fanout counts and intent:

```
QUERIES THIS CONTENT WOULD ANSWER (3 queries, 14 total fanouts)

Query                                    Fanouts    Intent
"best AI app builder pricing"            8          Commercial
"lovable vs bolt.new cost"               4          Commercial
"AI app builder ROI comparison"          2          Informational
```

Each row: query text in 11px, fanout count in JetBrains Mono 11px, intent as subtle pill.

Below queries: "These queries are tracked in Prompt Tracking after publishing" — 10px var(--text-secondary), linking to `/prompt-tracking`.

#### 7. Activity Log

Simple timeline of actions taken on this assignment:

```
ACTIVITY LOG

Mar 26, 2026  Created from gap analysis pipeline v2
Mar 26, 2026  Reviewed by shank keshri
```

Each entry: 10px, date in var(--text-secondary), action text. Simple vertical list with small dot markers.

#### 8. Actions (bottom, sticky or at scroll end)

```
[✓ Approve & Send to Studio]    [✗ Reject]
```

Two buttons only. No edit button.
- Approve: green background, white text, 12px font-weight 600
- Reject: transparent, red text, 1px red border

On approve: item removed from list, drawer closes, toast shown.
On reject: item moved to rejected list, drawer closes, toast shown.

---

## CUSTOM TOPIC MODAL

Opens when user clicks "+ Custom Topic". Animation: scaleIn 200ms. Backdrop: rgba(0,0,0,0.6).

### Step 1 — Define Topic

Full form:

**Topic Title** — text input, placeholder "e.g., How to Migrate from Bubble to Lovable"
**What should this content cover?** — textarea (3 rows), placeholder "Describe the angle, audience, or specific need..."
**Target Cluster** — dropdown of existing clusters + "+ New cluster" option
**Format** — button group: Guide / Comparison / Tutorial / Listicle / Case Study
**Funnel Stage** — button group: TOFU / MOFU / BOFU (colored)
**Primary Persona** — button group: Solo Founder / Product Manager / Agency Owner / Technical Engineer
**Intent** — button group: Informational / Commercial / Navigational / Transactional

Footer: [Cancel] [Analyze Citation Potential →] (accent button, disabled until title filled)

### Step 2 — AI Research (animated)

Show 5 research steps that tick through one by one (350ms apart):

```
✓ Scanning AI citations for related topics
✓ Identifying competitors in this space
○ Calculating citation opportunity
○ Matching persona affinity
○ Generating recommendation
```

Each step: circle indicator (green ✓ when complete, gray ○ when pending), text fades from muted to white on completion. Staggered animation.

### Step 3 — Results

Green success banner: "✓ Strong citation potential detected"

Two metric cards: Citation Opportunity (%) + Est. Citations (~N)

Top competitor card (if found): favicon + title + domain + word count + FAQ/Tables status. Or "No existing competition — first-mover opportunity" green card.

Footer: [Cancel] [✓ Add to Priority Queue] (green button)

On add: modal closes, item appears at appropriate rank in Priority Queue with source "custom", toast: "✓ Custom topic added to Priority Queue"

---

## STRATEGIC INITIATIVES

### Sidebar (opens from left, 340px wide)

Animation: slideRight 200ms from left edge. Backdrop: rgba(0,0,0,0.2).

Header: "Strategic Initiatives" (14px font-weight 600). Description: "Define strategic content directions. The AI researches your target space and generates ranked recommendations." (11px var(--text-secondary)).

"+ New Initiative" button — dashed purple border, purple text.

List of existing initiatives. Each card:
```
┌─ purple left border ─────────────────────┐
│ Technical Engineer Expansion              │
│ Target developers who use APIs and...     │
│ [Technical Engineer] [Agency Owner]       │
│ 4 assignments · Created Mar 15, 2026     │
└───────────────────────────────────────────┘
```

### New Initiative Modal

Opens on "+ New Initiative" click. Animation: scaleIn 200ms.

**Step 1:** Name (text input), Strategic Direction (textarea — "Describe the audience, topics, and goals"), Target Personas (multi-select buttons), Target Stages (multi-select buttons). Footer: [Cancel] [Research This Space →] (purple button).

**Step 2:** 5 animated research steps (same pattern as Custom Topic but purple-themed):
```
✓ Analyzing AI citations in target space
✓ Mapping competitor content landscape
○ Identifying underserved topics
○ Scoring citation opportunities
○ Generating content recommendations
```

**Step 3:** Purple success banner: "✓ Found 6 high-potential topics in this space". Description: "6 content recommendations will appear in your Priority Queue tagged as Strategic." Footer: [View in Priority Queue] (purple button). Closes modal + sidebar, switches to Priority Queue filtered by source="strategic".

---

## REJECTED TAB

Minimal. Small count in the tab label: "Rejected (2)".

Simple list of rejected items:
```
DP-R01  Scaling AI Apps: Performance Benchmarks     Low priority — revisit Q3     Mar 22     [↩ Restore]
```

Each row: ID + title + reason + date + restore button. Compact, single-line per item. "Restore" puts the item back in the Priority Queue.

No special styling, no cards, no expanded view. This is a reference list, not a primary interaction.

---

## TOAST NOTIFICATIONS

On approve: green-tinted toast at bottom-center, "✓ 3 topics approved → Content Studio", auto-dismiss 3s. Animation: fadeUp 200ms.
On reject: same pattern but text: "✗ 2 topics rejected".
On custom topic add: "✓ Custom topic added to Priority Queue".
On initiative complete: "✓ 6 topics generated from initiative".

---

## SHARE FUNCTIONALITY

Every assignment has a shareable link. The share button (🔗 icon) in the drawer header copies `https://app.deeppresence.com/planner/{id}` to clipboard and shows a brief "✓ Copied" tooltip (1.5s).

In production, this link would open the app and auto-open the drawer for that specific assignment. For now, just copy the URL and show the tooltip.

---

## CLUSTERS & SUBCLUSTERS (Mock Data)

```typescript
const CLUSTERS = [
  { id: "cl1", name: "Competitive Landscape", subclusters: [
    { id: "sc1", name: "Platform Comparisons", citOpp: 0.85 },
    { id: "sc2", name: "Pricing & Value", citOpp: 0.82 },
  ]},
  { id: "cl2", name: "Platform Capabilities", subclusters: [
    { id: "sc3", name: "Database & Backend Integration", citOpp: 0.78 },
    { id: "sc4", name: "UI/UX Generation", citOpp: 0.71 },
    { id: "sc5", name: "Code Generation Quality", citOpp: 0.76 },
  ]},
  { id: "cl3", name: "Security & Compliance", subclusters: [
    { id: "sc6", name: "Data Privacy & GDPR", citOpp: 0.68 },
    { id: "sc7", name: "SOC 2 & Enterprise Security", citOpp: 0.65 },
  ]},
  { id: "cl4", name: "Developer Experience", subclusters: [
    { id: "sc8", name: "API Integration Patterns", citOpp: 0.74 },
    { id: "sc9", name: "Code Export & Customization", citOpp: 0.70 },
    { id: "sc10", name: "Developer Documentation", citOpp: 0.66 },
  ]},
  { id: "cl5", name: "Deployment & Operations", subclusters: [
    { id: "sc11", name: "CI/CD & Hosting", citOpp: 0.72 },
    { id: "sc12", name: "Scaling & Performance", citOpp: 0.61 },
  ]},
];
```

---

## STRATEGIC INITIATIVES (Mock Data)

```typescript
const INITIATIVES = [
  {
    id: "init1", name: "Technical Engineer Expansion",
    description: "Target developers who use APIs and code export",
    personas: ["te", "da"],
    assignmentCount: 4, created: "Mar 15, 2026",
  },
  {
    id: "init2", name: "Enterprise Security Push",
    description: "Build authority in compliance for enterprise buyers",
    personas: ["pm"],
    assignmentCount: 3, created: "Mar 8, 2026",
  },
];
```

---

## ASSIGNMENT MOCK DATA

Use EXACTLY these 10 assignments. Do not modify titles, clusters, or scores. Copy the full data structure from the prototype (content-planner-v5.jsx) including:
- All 10 assignments with IDs DP-001 through DP-010
- DP-009 (Stripe Payments) has empty competitors array — this is the "new territory" example
- DP-010 (Migrate from Bubble) has source "custom" — this is the custom topic example
- DP-003, DP-005, DP-009, DP-011 have initiative "Technical Engineer Expansion"
- DP-004, DP-007 have initiative "Enterprise Security Push"
- Each assignment has exactly 3 relatedQueries with fanout counts and intent types
- Each assignment has exactly 3 reasons (title + text)
- Each assignment has an activityLog array

For the `relatedQueries` field, expand from simple strings to objects:

```typescript
relatedQueries: [
  { query: "best AI app builder pricing", fanouts: 8, intent: "Commercial" },
  { query: "lovable vs bolt.new cost", fanouts: 4, intent: "Commercial" },
  { query: "AI app builder ROI comparison", fanouts: 2, intent: "Informational" },
],
```

For the `activityLog` field:
```typescript
activityLog: [
  { action: "Created from gap analysis pipeline v2", date: "Mar 18, 2026", by: "System" },
  { action: "Reviewed by shank keshri", date: "Mar 26, 2026", by: "shank keshri" },
],
```

Add 2 rejected items:
```typescript
const REJECTED = [
  { id: "DP-R01", title: "Scaling AI Apps: Performance Benchmarks", cluster: "Deployment & Operations", reason: "Low priority — revisit Q3", date: "Mar 22" },
  { id: "DP-R02", title: "Data Privacy in AI Builders: How Platforms Handle Your Data", cluster: "Security & Compliance", reason: "Overlaps with GDPR guide (DP-007)", date: "Mar 20" },
];
```

---

## BRAND SYSTEM RULES

- CSS variables for ALL UI colors — never hardcode hex
- 1px borders on all cards — no borderless, no shadows, no gradients
- JetBrains Mono for ALL data values (IDs, scores, citations, percentages)
- Space Grotesk for ALL text (titles, labels, descriptions)
- Real brand logos via Google Favicon API for ALL competitor domains
- Do NOT set `crossOrigin="anonymous"` on favicon images
- Light + dark mode via CSS variables
- Source badge colors: gap = accent/teal, strategic = purple, custom = gray
- Stage pill colors: TOFU = teal, MOFU = amber, BOFU = green
- Effort pill colors: low = green, medium = amber, high = red
- Intent pill: subtle styling, 9px, thin border only

---

## VERIFICATION

```bash
npm run dev
npx tsc --noEmit
```

1. Page loads at `/planner` with Priority Queue as default view
2. Filter bar: Stage + Persona + Source filters work, "× Clear" appears when active
3. View toggle: Priority Queue / Cluster Explorer / Rejected switches correctly
4. Priority Queue: 10 rows with all columns, 44px row height, two-line titles work
5. Sorting: click Score or Est. Cit. headers to toggle sort direction
6. Checkboxes: select all selects ALL items, bulk action bar appears with count
7. Bulk approve: selected items removed, toast shown
8. Row click: drawer opens (slideRight animation)
9. Drawer: ID + all pills in header, share button copies link with tooltip
10. Drawer: 2 metric cards (Est. Citations with mini bar graphic, Citation Opportunity with description)
11. Drawer: "Why We Recommend" — 3 horizontal cards with amber top border
12. Drawer: Competitors with clickable URLs, OR "New Territory" green card
13. Drawer: Persona Affinity 2×2 grid with percentages, full names, progress bars
14. Drawer: Queries with fanout counts and intent labels
15. Drawer: Activity Log with timeline entries
16. Drawer: Approve + Reject buttons (no edit button)
17. Cluster Explorer: tree collapses/expands with animation
18. Cluster Explorer: subcluster selection shows assignments as lean rows
19. Cluster Explorer: sort dropdown (Highest Score / Most Citations / Opportunity)
20. Cluster Explorer: inline ✓/✗ buttons per row
21. "+ Custom Topic" opens modal with 3-step flow (form → research animation → results)
22. "✦ Initiatives" opens sidebar with existing initiatives
23. "+ New Initiative" opens modal with 3-step flow (form → research animation → results)
24. Rejected tab: minimal list with restore buttons
25. Toast notifications on all approve/reject/add actions
26. All animations smooth (fadeUp rows, slideRight drawer, scaleIn modals)
27. All competitor favicons loading
28. All content IDs visible (DP-XXX format)
29. Works in both light and dark mode
30. `npm run build` succeeds

---

## COMPLETION CRITERIA

- [ ] Page loads at `/planner` with no console errors
- [ ] Priority Queue: 10 rows, all columns, sorting, checkboxes, bulk actions
- [ ] Cluster Explorer: tree navigation, lean assignment rows, sort dropdown, inline approve/reject
- [ ] Rejected tab: minimal list with restore functionality
- [ ] Detail Drawer: all 8 sections (header, metrics, reasons, competitors, personas, queries, log, actions)
- [ ] "New Territory" card renders for DP-009 (empty competitors)
- [ ] Custom Topic Modal: 3-step flow with form, animated research, results
- [ ] Strategic Initiative Sidebar: list of initiatives, "+ New Initiative" button
- [ ] New Initiative Modal: 3-step flow with form, animated research, results
- [ ] Share button: copies link, shows tooltip
- [ ] Content IDs: visible in table, drawer, cluster explorer
- [ ] Intent pills: Informational/Commercial/Navigational/Transactional in table + drawer
- [ ] Queries section: expanded with fanout counts and intent per query
- [ ] Activity Log: timeline entries in drawer
- [ ] Filter bar: Stage + Persona + Source filters work correctly
- [ ] All animations: fadeUp rows, slideRight drawer, scaleIn modals, barGrow scores
- [ ] Toast notifications: approve, reject, add custom, complete initiative
- [ ] All competitor favicons loading (Google Favicon API)
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts, real logos
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds