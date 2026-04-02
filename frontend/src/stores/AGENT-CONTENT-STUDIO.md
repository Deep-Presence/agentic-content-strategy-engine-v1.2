# Agent — Content Studio Page (Production Build)

> **Read CLAUDE.md and brand-system.md first, then this file.** This is a FULL REBUILD of `/content-studio`.

---

## Mission

Content Studio is where content moves through production. Items arrive from Content Planner, bounce between human review gates and agent work stages, and exit as published content.

**Three-column board:**
- **Queue** — Items from Content Planner awaiting the user's commitment to produce. Nothing changes in the card until the user starts it. This is a staging area, not a review gate.
- **Your Review** — Items waiting for human action (brief approval or article approval)
- **Agent Work** — Items being processed by agents (planning, brief generation, writing, evaluating)

Cards auto-move between columns. The user never drags cards. Approving moves a card forward; agents completing work moves a card to Your Review.

**Full-page editor:** Clicking ANY card opens a full-page view. For article review, this is a **BlockNote** block editor — full Notion-style editing with slash commands, drag-and-drop blocks, formatting toolbar. For other stages, the full-page view adapts its content but keeps the same shell.

---

## Files You Own

```
src/app/(dashboard)/content-studio/page.tsx
src/app/(dashboard)/content-studio/_components/
```

**DELETE** whatever currently exists at this route. Full rebuild.

---

## INSTALL BLOCKNOTE

Before building, install BlockNote with the shadcn UI package:

```bash
npm install @blocknote/core @blocknote/react @blocknote/shadcn
```

Do NOT install `@blocknote/mantine`. We use the shadcn package for Tailwind/Radix compatibility.

Import pattern:
```typescript
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/shadcn";
import "@blocknote/shadcn/style.css";
```

The editor must use our dark theme. BlockNote supports `theme="dark"` prop on `<BlockNoteView>`. Override CSS variables as needed to match brand-system.md colors.

---

## MANDATORY LAYOUT STANDARDS

Same density rules as all other pages:

```
Page horizontal padding: max 24px
Section gaps: 16px
Card internal padding: 12px 14px
Table headers: 11px uppercase, letter-spacing 0.05em
Card title: 13px font-weight 500
Card metadata: 11px var(--text-secondary)
KPI values: 22px JetBrains Mono font-weight 700
Pill/badge text: 9px uppercase font-weight 600
All data values: JetBrains Mono
All text: Space Grotesk
1px borders on everything
CSS variables for all colors
```

---

## PAGE STRUCTURE

### Header Bar (48px)

```
Content Studio    Week of March 10 — Cycle 12 ▾    [+ New Cycle]
```

Left: "Content Studio" (16px font-weight 600). Center: cycle selector dropdown. Right: "+ New Cycle" button (teal outline).

### KPI Strip (4 cards)

```
IN QUEUE          PUBLISHED          AVG. CITATION SCORE     CYCLE PROGRESS
4 items           14 this cycle      61 across engines       24%
```

Each card: 1px border, surface background, label (9px uppercase dim), value (22px JetBrains Mono), subtitle (11px dim). Colors: published = green, citation score = teal, progress = amber.

### Filter Bar (40px)

Left: cycle date range. Right: filter pills (All / Briefs / Articles / By cluster), sort dropdown (Priority / Newest / Gap score).

### Three-Column Board

Column widths: Queue 22% | Your Review 39% | Agent Work 39%. Separated by 1px vertical borders. Each column scrolls independently.

**Column headers:**
- Queue: "Queue" + count badge (neutral) + "Items from Content Planner"
- Your Review: "Your review" + count badge (teal) + "Approve or send back"
- Agent Work: "Agent work" + count badge (amber) + "Automated generation in progress"

---

## CARD COMPONENT

Every card follows the same structure. The card is the atomic unit of the board.

### Card Layout

```
┌─────────────────────────────────────────────────┐
│ Title (13px, font-weight 500, max 2 lines)      │
│ IH-001 · Competitive Landscape      (11px, dim) │
│                                                  │
│ [COMPARISON] [P0] ~12 ⏱ 10min  retool.com   87 │
│                                                  │
│ ● Brief ready for review  (human review cards)   │
│ — OR —                                           │
│ Writing — section 4 of 7   34%  [████░░░░░]     │
│ 1,194 / 3,500 words · 3/7 sections (agent cards)│
└─────────────────────────────────────────────────┘
```

### Card Styling

- Background: var(--card)
- Border: 1px solid var(--border), 6px border-radius
- Left border accent (3px):
  - Queue: var(--text-secondary) — neutral
  - Brief review: var(--amber)
  - Article review: var(--accent) / teal
  - Agent work: var(--surface) — subtle
- Hover: var(--hover) background, border lightens, 150ms transition
- Cursor: pointer (entire card clickable)

### Card Data Fields

```typescript
interface ContentCard {
  id: string;                    // "IH-001" — brand-initial format
  title: string;
  type: "HOW_TO" | "COMPARISON" | "GUIDE" | "LONG_BLOG" | "PILLAR_PAGE";
  cluster: string;
  gap: number;                   // 0-1
  score: number;                 // 0-100
  priority: "P0" | "P1" | "P2";
  readTime: number;              // minutes
  competitor: string;            // domain
  column: "queue" | "human" | "agent";
  stage: ContentStage;
  stageLabel: string;
  agentProgress?: AgentProgress;
  briefContent?: BriefContent;
  articleContent?: ArticleContent;
  metadata?: ContentMetadata;
}

type ContentStage =
  | "queue"
  | "planning"
  | "brief_generation"
  | "brief_review"
  | "writing"
  | "evaluating"
  | "article_review"
  | "published";

interface AgentProgress {
  pct: number;
  currentTask: string;
  wordsCurrent?: number;
  wordsTarget?: number;
  sectionsComplete?: number;
  sectionsTotal?: number;
}
```

### Card Tags Row

- Type pill: teal-dim background, teal text (HOW-TO, COMPARISON, GUIDE, LONG BLOG, PILLAR PAGE)
- Priority pill: amber-dim background, amber text (P0, P1, P2)
- Gap: `~NN` in red, JetBrains Mono 10px font-weight 600 (multiply decimal by 100)
- Read time: clock SVG icon + "Nmin" in dim
- Competitor: domain text in var(--text-secondary)
- Score: right-aligned, JetBrains Mono 11px

### Agent Progress (bottom of agent cards)

- Stage label with typing animation: "Writing — section 4 of 7" (10px, amber, font-weight 500)
- Progress percentage right-aligned (10px, JetBrains Mono, dim)
- Progress bar: 4px height, surface background, colored fill
  - Fill color: <50% amber, 50-80% teal, >80% green
  - CSS pulsing animation on the fill
- Word count + section count below (10px, JetBrains Mono, dim)

### Human Review Indicator (bottom of human review cards)

- Colored dot (6px circle) + text label
- Brief review: amber dot + "Brief ready for review" (amber, 11px)
- Article review: teal dot + "Article ready for review" (teal, 11px)

---

## CARD MOVEMENT LOGIC

Cards auto-move. The user NEVER manually drags cards.

```
QUEUE ──[user: "Start"]──→ AGENT WORK (stage: planning)
                                 │
                     [agent completes planning + brief]
                                 │
                                 ▼
YOUR REVIEW (stage: brief_review) ←──┘
       │
       ├──[user: "Approve brief"]──→ AGENT WORK (stage: writing)
       │                                  │
       │                      [agent completes writing + eval]
       │                                  │
       │                                  ▼
       │                     YOUR REVIEW (stage: article_review) ←──┘
       │                             │
       │                             ├──[user: "Approve"]──→ PUBLISHED
       │                             ├──[user: "Publish"]──→ PUBLISHED
       │                             └──[user: "Send back + feedback"]──→ AGENT WORK (revision)
       │
       └──[user: "Send back"]──→ AGENT WORK (brief revision)
```

### Movement Animation

- Card fading out: 200ms fade + scale to 0.95
- Card appearing in target: 300ms fadeUp + scale from 0.95
- Column count badges update simultaneously

---

## FULL-PAGE VIEW

Opens when clicking any card. The shell is consistent — content adapts by stage.

### Shell Layout

```
┌────────────────────────────────────────────────────────────────────┐
│ TOP BAR: ← Back | Title | Type · Cluster · Score | Stage | Actions│
├────────────────────────────────────────────────────────────────────┤
│ [Agent banner — only when agent is working]                        │
├──────────────┬──────────────────────────┬──────────────────────────┤
│ LEFT SIDEBAR │     CENTER CONTENT       │    RIGHT SIDEBAR         │
│ (260px)      │     (flex: 1)            │    (300px, tabbed)       │
│              │                          │                          │
│ Section nav  │  BlockNote editor /      │  [Metrics] [SEO] [Links] │
│ or brief     │  brief review /          │  [Export]                │
│ outline      │  progress view           │                          │
├──────────────┴──────────────────────────┴──────────────────────────┤
│ BOTTOM BAR: Send back | Re-run | Approve | Publish                 │
└────────────────────────────────────────────────────────────────────┘
```

### Top Bar (52px)

- Left: "← Back" button (closes full view)
- Center-left: title (14px font-weight 600), subtitle line: `TYPE · Cluster · Score NN · Gap ~NN`
- Right: stage badge (colored by stage) + primary action buttons

Stage badge colors:
- Queue: neutral (surface bg, dim text)
- Brief review: amber
- Article review: teal
- Agent working: amber with pulse animation
- Published: green

### Agent Working Banner

Only visible when `column === "agent"`. Full-width, 44px, amber-dim background.

```
Agent working: Writing section 4: Tax Implications by Jurisdiction    [████████░░░░]  34%
```

Typing animation on task text. Progress bar inline (max-width 300px). Percentage right-aligned.

### Left Sidebar (260px)

**Queue stage:** Opportunity summary — gap score, priority, read time, "Why this topic" reasons from Content Planner, competitor analysis snippet.

**Brief review stage:** "Brief outline" header. Numbered list of proposed sections (clickable). "Sources across AI engines" — cards with engine count badges. "Why we picked this" — reason list.

**Article review stage (EDITOR):** "Sections" header. Section navigation list — each shows heading text + word count (JetBrains Mono). Active section: teal highlight, teal left border. Click to scroll in the BlockNote editor.

**Agent working stage:** Progress details, completed stages checklist, current task.

### Center Content Panel

**Queue stage:** Title, description, key metrics grid (gap, priority, read time, competitor).

**Brief review stage:** Title, "Why we picked this" reason cards, key success indicators (target words, exemplar count), full brief content.

**Article review stage — BLOCKNOTE EDITOR:**

This is the most important view. Use BlockNote with `@blocknote/shadcn`:

```typescript
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/shadcn";
import "@blocknote/shadcn/style.css";

function ArticleEditor({ content }) {
  const editor = useCreateBlockNote({
    initialContent: content, // BlockNote JSON blocks
  });

  return (
    <BlockNoteView
      editor={editor}
      theme="dark"
      // Override CSS vars to match brand-system.md
    />
  );
}
```

The editor should:
- Fill the center panel width (max-width 720px, centered)
- Use our dark theme colors via CSS variable overrides
- Support all standard blocks: paragraph, H1-H3, bullet list, numbered list, table, code block, blockquote, image
- Show the slash command menu on "/"
- Show the floating formatting toolbar on text selection (Bold, Italic, Link, H2, H3, Quote + Regenerate, Rewrite, Shorten, Expand, Tone — the AI toolbar from the screenshot)
- Support drag-and-drop block reordering
- Export to Markdown and HTML for the download flow

**AI toolbar buttons** (Regenerate, Rewrite, Shorten, Expand, Tone) are placeholders that will connect to the agent API. For now, show the buttons in the floating toolbar but make them no-ops with a tooltip "Coming soon — agent integration."

**Agent working stage:** Title, large progress card, section-by-section progress, "Content will be available for review once complete."

### Right Sidebar (300px, TABBED)

Four tabs at the top: **Metrics** | **SEO** | **Links** | **Export**

#### Metrics Tab (default)

**Citation Prediction:**
- Horizontal bar chart — one bar per engine (ChatGPT, Claude, Perplexity, Google AI, Gemini)
- Each bar: engine name (11px) + bar + score (JetBrains Mono 11px)
- Color: >60 green, 50-60 teal, <50 red
- Average score as large number below (20px JetBrains Mono)

**Structural Compliance:**
- Progress bars for: Word count, Headers, Citations, Stats/data points
- Each: label (11px) + "current/target" (JetBrains Mono 11px) + bar
- Bar color: >90% green, 70-90% teal, <70% amber

**Voice Compliance:**
- Single progress bar + percentage (14px JetBrains Mono teal)

**E-E-A-T Score:**
- Overall score (0-100, 18px JetBrains Mono)
- Breakdown: Experience, Expertise, Authoritativeness, Trustworthiness — each with small bar

#### SEO Tab

- **Slug URL:** Editable text field, `/blog/pro-rata-rights-explained`
- **Meta title:** Editable, character count (60 char target), color-coded count
- **Meta description:** Editable textarea, character count (155 char target)
- **OG Image:** Thumbnail preview or "Generate" button
- **Canonical URL:** Auto-generated, editable
- **Schema markup:** Toggle (applied / not applied)
- **Publish date:** Date picker
- **Author:** Text field
- **Tags:** Tag pills with add/remove

```typescript
interface ContentMetadata {
  slug: string;
  metaTitle: string;         // target 60 chars
  metaDescription: string;   // target 155 chars
  ogImageUrl?: string;
  canonicalUrl: string;
  schemaMarkup: boolean;
  publishDate?: string;
  author?: string;
  tags: string[];
}
```

#### Links Tab

**Interlink Suggestions:**
- Checkbox list of internal links
- Each: checkbox + title (teal) + path (JetBrains Mono dim)
- Checked = already inserted by agent
- Unchecked = suggested but not yet added

**External Citations:**
- List of cited sources with domains and favicon

#### Export Tab

**Copy:**
- "Copy as Markdown" button
- "Copy as HTML" button
- "Copy as plain text" button
- Each shows "✓ Copied" feedback for 1.5s

**Download:**
- "Download .md" button
- "Download .html" button

**Publish:**
- If CMS connected: "Publish to [CMS name]" primary green button
- If no CMS: "Mark as Published" button that opens a small form:
  ```
  Published this content? Paste the live URL so we can track citations.
  [URL input field]
  [Confirm — Start Tracking]
  ```
  On confirm: card moves to Published state, URL gets registered for citation tracking.

### Bottom Action Bar (56px)

Fixed at bottom. var(--card) background, top border.

Buttons adapt by stage:
- **Queue:** [Start Production] (teal)
- **Brief review:** [Send back] | [Approve brief] (amber)
- **Article review:** [Send back with feedback] | [Approve] (teal) | [Publish] (green)
- **Agent working:** [Cancel] (red outline) — only action
- **Published:** [Edit] | [View live ↗] | [Unpublish]

---

## CYCLE MANAGEMENT

### Cycle Selector (header dropdown)

Shows list of cycles: "Week of March 10 — Cycle 12 (Active)", "Week of March 3 — Cycle 11", etc.

Active cycle shows all columns. Past cycles show a **cycle archive view**:

```
Cycle 11 Results
12 articles published · 67 total citations earned · +0.8% SOV lift

[Card grid of published articles with citation counts]
```

### New Cycle

"+ New Cycle" button creates a new cycle dated from next week. Items in Queue carry over to the new cycle.

---

## MOCK DATA

### Cycle

```typescript
const MOCK_CYCLE = {
  id: "cycle-012",
  name: "Cycle 12",
  weekOf: "2026-03-10",
  status: "active",
  stats: { total: 58, queue: 4, humanReview: 5, agentWork: 21, published: 14, avgCitationScore: 61, completionPct: 24 },
};
```

### Queue Items (2)

```typescript
{ id: "IH-009", title: "RBAC Accuracy in AI-Generated Applications", type: "HOW_TO", cluster: "Boundary", gap: 0.130, score: 85, priority: "P2", readTime: 8, competitor: "auth0.com", column: "queue", stage: "queue", stageLabel: "From content planner" },
{ id: "IH-010", title: "Webhook Security for AI-Powered Integrations", type: "GUIDE", cluster: "Security", gap: 0.165, score: 90, priority: "P1", readTime: 12, competitor: "snyk.io", column: "queue", stage: "queue", stageLabel: "From content planner" },
```

### Human Review Items (2)

```typescript
{
  id: "IH-001", title: "Audit Logs & Change History for AI App Builders",
  type: "COMPARISON", cluster: "Boundary", gap: 0.122, score: 87, priority: "P0", readTime: 10, competitor: "retool.com",
  column: "human", stage: "brief_review", stageLabel: "Brief ready for review",
  briefContent: {
    sections: ["Introduction to audit logging", "Why AI builders need change tracking", "Feature comparison matrix", "Implementation patterns", "Compliance requirements", "Best practices", "Conclusion"],
    targetWords: 2800, exemplarCount: 2,
    sources: [{ name: "Retool Audit Guide", domain: "retool.com", engines: 3 }, { name: "Zapier Change Tracking", domain: "zapier.com", engines: 2 }],
    reasons: ["Competitors cited 3.2x more on this cluster — significant gap", "1 high-quality exemplar (1,224 words, 11 headers)", "How-to format has 86% citation correlation"],
  },
},
{
  id: "IH-002", title: "Pro-Rata Rights Explained: What Every Founder Needs to Know",
  type: "LONG_BLOG", cluster: "Definition", gap: 0.098, score: 88, priority: "P0", readTime: 14, competitor: "carta.com",
  column: "human", stage: "article_review", stageLabel: "Article ready for review",
  articleContent: {
    wordCount: 3323, targetWords: 3500, voiceCompliance: 72,
    sections: [
      { heading: "What are pro-rata rights?", words: 420, content: "Pro-rata rights give existing investors the option to participate in future funding rounds to maintain their ownership percentage. Understanding how these rights work — and when to grant them — is critical for founders navigating Series A and beyond.\n\nA pro-rata right (also called a participation right or pre-emptive right) is a contractual provision that allows an investor to invest additional capital in subsequent financing rounds." },
      { heading: "How pro-rata calculations work", words: 380, content: "If an investor owns 10% of a company and the company raises a $5M Series B, the investor's pro-rata allocation would be $500,000 (10% × $5M). This allows them to maintain their 10% ownership stake post-dilution.\n\nThe formula: Pro-rata allocation = Current ownership % × New round size." },
      { heading: "Standard terms by round", words: 510, content: "Pro-rata terms evolve across funding stages. At seed, pro-rata rights are rare — most SAFE agreements don't include them by default. By Series A, they become standard for lead investors and are typically included in the investors' rights agreement." },
      { heading: "When to grant (and not grant)", words: 440, content: "Granting pro-rata rights to early investors aligns incentives — investors who can maintain ownership are more motivated to help the company succeed. However, over-committing pro-rata rights can create problems in later rounds." },
      { heading: "Pro-rata in your term sheet", words: 390, content: "In your term sheet, pro-rata rights will typically appear in the investors' rights agreement rather than the certificate of incorporation." },
      { heading: "Pitfalls and negotiation tactics", words: 480, content: "The most common pitfall is granting broad pro-rata rights to too many small investors at the seed stage. When Series A arrives, you may find that 40% of the round is already spoken for." },
      { heading: "Real-world examples", words: 350, content: "Company A granted rights to all 12 seed investors, consuming 35% of the Series A. Company B limited rights to their lead seed investor only, giving maximum flexibility." },
      { heading: "Key takeaways", words: 353, content: "Limit rights to lead investors at each stage, understand the cumulative impact on future rounds, and always model dilution implications before committing." },
    ],
    citPrediction: [
      { engine: "ChatGPT", score: 62 }, { engine: "Claude", score: 58 },
      { engine: "Perplexity", score: 65 }, { engine: "Google AI", score: 50 },
      { engine: "Gemini", score: 55 },
    ],
    compliance: [
      { label: "Words", current: 3323, target: 3500 },
      { label: "Headers", current: 11, target: 12 },
      { label: "Citations", current: 13, target: 15 },
      { label: "Stats", current: 8, target: 10 },
    ],
    eeat: { overall: 76, experience: 70, expertise: 82, authoritativeness: 78, trustworthiness: 74 },
    interlinks: [
      { title: "Cap table management guide", path: "/blog/cap-table-management", linked: true },
      { title: "Equity compensation basics", path: "/blog/equity-compensation-101", linked: false },
      { title: "409A valuation process", path: "/blog/409a-valuations", linked: false },
      { title: "Series A fundraising checklist", path: "/blog/series-a-checklist", linked: true },
    ],
  },
  metadata: {
    slug: "pro-rata-rights-explained",
    metaTitle: "Pro-Rata Rights Explained: What Every Founder Needs to Know",
    metaDescription: "Learn how pro-rata rights work, when to grant them, and how they affect your cap table. A complete guide for founders navigating Series A and beyond.",
    canonicalUrl: "https://insighthealth.com/blog/pro-rata-rights-explained",
    schemaMarkup: true, publishDate: "2026-03-15", author: "Insight Health Team",
    tags: ["pro-rata rights", "fundraising", "term sheets", "series A"],
  },
},
```

### Agent Work Items (4)

```typescript
{ id: "IH-003", title: "International Equity Grants: Tax Compliance Guide", type: "PILLAR_PAGE", cluster: "Mechanism", gap: 0.175, score: 93, priority: "P0", readTime: 15, competitor: "deel.com", column: "agent", stage: "writing", stageLabel: "Writing — section 4 of 7", agentProgress: { pct: 34, currentTask: "Writing section 4: Tax Implications by Jurisdiction", wordsCurrent: 1194, wordsTarget: 3500, sectionsComplete: 3, sectionsTotal: 7 } },
{ id: "IH-004", title: "Secrets & Environment Variables in Prompt-to-App Tools", type: "HOW_TO", cluster: "Mechanism", gap: 0.175, score: 91, priority: "P1", readTime: 8, competitor: "netlify.com", column: "agent", stage: "brief_generation", stageLabel: "Generating brief", agentProgress: { pct: 60, currentTask: "Analyzing exemplar structure" } },
{ id: "IH-005", title: "SOC 2 + GDPR for AI Development Platforms", type: "GUIDE", cluster: "Boundary", gap: 0.159, score: 89, priority: "P2", readTime: 12, competitor: "vanta.com", column: "agent", stage: "planning", stageLabel: "Planning — analyzing queries", agentProgress: { pct: 20, currentTask: "Analyzing 200 query scorecards" } },
{ id: "IH-006", title: "Bolt.new Alternatives 2026: Complete Comparison", type: "COMPARISON", cluster: "Category", gap: 0.141, score: 92, priority: "P1", readTime: 10, competitor: "g2.com", column: "agent", stage: "evaluating", stageLabel: "Evaluating — cycle 1", agentProgress: { pct: 85, currentTask: "Eval: structural 0.82, semantic 0.78, style 0.85" } },
```

---

## AGENT PROGRESS SIMULATION

For the prototype, simulate agent progress with a `setInterval` that increments progress every 3 seconds. When progress hits 100%:

- `planning` or `brief_generation` → move card to `human` column, `brief_review` stage
- `writing` or `evaluating` → move card to `human` column, `article_review` stage

Generate mock brief/article content when the agent "completes."

---

## ANIMATIONS

```css
@keyframes fadeUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
@keyframes slideUp { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
@keyframes progressPulse { 0%,100% { opacity:1; } 50% { opacity:0.65; } }
@keyframes cardMove { 0% { opacity:0; transform:scale(0.95) translateY(-8px); } 100% { opacity:1; transform:scale(1) translateY(0); } }
@keyframes typing { 0% { opacity:0.3; } 50% { opacity:1; } 100% { opacity:0.3; } }
```

- Cards entering a column: `cardMove 300ms ease`
- Agent task text: `typing 1.8s ease-in-out infinite`
- Progress bar fill: `progressPulse 2.5s ease-in-out infinite`
- Full-page view open: `slideUp 250ms ease`
- All hover transitions: 150ms

---

## BLOCKNOTE EDITOR CUSTOMIZATION

### Dark Theme

Override BlockNote's CSS variables to match our brand system:

```css
[data-color-scheme="dark"] .bn-container {
  --bn-colors-editor-text: var(--text-primary);
  --bn-colors-editor-background: var(--background);
  --bn-colors-menu-background: var(--surface);
  --bn-colors-menu-text: var(--text-primary);
  --bn-colors-tooltip-background: var(--surface);
  --bn-colors-tooltip-text: var(--text-primary);
  --bn-colors-hovered-background: var(--hover);
  --bn-colors-selected-background: var(--accent-subtle);
  --bn-colors-disabled-background: var(--border);
  --bn-colors-disabled-text: var(--text-secondary);
  --bn-colors-shadow: none;
  --bn-border-radius: 4px;
  --bn-font-family: 'Space Grotesk', sans-serif;
}
```

### Custom Slash Menu Items

Add these custom slash menu entries (in addition to defaults):
- `/citation` — Insert a citation callout block (teal left border, source attribution)
- `/comparison` — Insert a comparison table (2-column layout)
- `/stat` — Insert a statistic highlight block (large number + description)

These are custom blocks — use BlockNote's custom block API:

```typescript
const CitationBlock = createReactBlockSpec({
  type: "citation",
  propSchema: { source: { default: "" }, text: { default: "" } },
  content: "inline",
});
```

### Content Serialization

The editor content must be serializable to:
- BlockNote JSON (for storage and re-editing)
- Markdown (for download and CMS publishing)
- HTML (for download and CMS publishing)

Use BlockNote's built-in conversion:
```typescript
const markdown = await editor.blocksToMarkdownLossy(editor.document);
const html = await editor.blocksToHTMLLossy(editor.document);
```

---

## PUBLISH FLOW

### Scenario 1: Manual Download + URL Tracking

1. User clicks "Download .md" or "Download .html" in Export tab
2. File downloads to their machine
3. Card stays in "Article Review" state
4. User publishes manually on their site
5. User clicks "Mark as Published" in Export tab
6. Modal appears: "Paste the live URL so we can track citations"
7. User enters URL, clicks "Confirm — Start Tracking"
8. Card moves to Published state with the URL
9. Citation tracking begins for that URL

### Scenario 2: CMS Integration (future)

Show a "Connect CMS" placeholder in the Export tab:
```
Connect your CMS to publish directly from Content Studio.
Supported: WordPress, Webflow, Ghost, Custom API
[Connect CMS — Coming Soon]
```

### Published State

Published cards are removed from the active board. They appear in the **cycle archive view** when viewing past cycles, showing:
- Title, publish date, live URL
- Citations earned (updates over time from Citation Intelligence data)
- Platforms that cite it (favicon badges)

---

## VERIFICATION

```bash
npm install @blocknote/core @blocknote/react @blocknote/shadcn
npm run dev
npx tsc --noEmit
```

1. Page loads at `/content-studio` with three-column board
2. KPI strip: 4 metrics with correct formatting
3. Cycle selector in header works
4. Filter bar with sort dropdown works
5. Queue column: 2 cards with neutral left border
6. Human Review column: 1 brief review (amber) + 1 article review (teal)
7. Agent Work column: 4 cards with progress bars and pulsing animation
8. Agent progress simulation: cards move to Human Review when progress hits 100%
9. Card click: opens full-page view with slideUp animation
10. Queue full-page: shows opportunity summary with metrics
11. Brief review full-page: left sidebar shows outline + sources, center shows reasons + brief
12. Article review full-page: BlockNote editor loads with dark theme
13. BlockNote: slash commands work ("/"), floating toolbar on text selection
14. BlockNote: blocks are draggable, support H1-H3, lists, tables, code, blockquote
15. Right sidebar tabs: Metrics / SEO / Links / Export all render correctly
16. Metrics tab: citation prediction bars, structural compliance, voice, E-E-A-T
17. SEO tab: editable slug, meta title (with char count), meta description, tags
18. Links tab: interlink checkboxes
19. Export tab: Copy MD/HTML/plain text buttons, Download MD/HTML buttons
20. Export tab: "Mark as Published" with URL input flow
21. Bottom action bar: buttons adapt by stage
22. "Approve brief" moves card from Human → Agent
23. "Approve article" + "Publish" moves card to Published
24. "Send back" moves card from Human → Agent
25. "Start Production" moves card from Queue → Agent
26. All movement has fade/scale animation
27. Agent working banner shows on agent stage full-page views
28. Empty state in "Your Review" when all items approved ("All caught up ✓")
29. BlockNote dark theme matches brand-system.md colors
30. All animations smooth
31. `npm run build` succeeds

---

## COMPLETION CRITERIA

- [ ] Three-column board renders with correct widths and independent scroll
- [ ] Cards show all data fields with correct styling
- [ ] Agent cards have animated progress bars
- [ ] Card auto-movement works for all stage transitions
- [ ] Movement animations (fade out + fade in)
- [ ] Full-page view opens on card click
- [ ] Full-page adapts by stage (queue, brief review, article review, agent working)
- [ ] BlockNote editor loads with dark theme in article review
- [ ] BlockNote slash commands and floating toolbar work
- [ ] BlockNote blocks are draggable and reorderable
- [ ] Right sidebar has 4 working tabs
- [ ] Metrics tab: citation prediction + compliance + voice + E-E-A-T
- [ ] SEO tab: all metadata fields editable with character counts
- [ ] Links tab: interlink suggestions with checkboxes
- [ ] Export tab: copy/download buttons + publish flow with URL input
- [ ] Bottom action bar: contextual buttons per stage
- [ ] KPI strip: 4 metrics
- [ ] Cycle selector dropdown in header
- [ ] Agent progress simulation (setInterval, cards move on completion)
- [ ] Brand-initial IDs (IH-XXX format)
- [ ] All text sizes match brand-system.md
- [ ] All colors from CSS variables
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds