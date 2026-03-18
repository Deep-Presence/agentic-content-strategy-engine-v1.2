# Agent 5 — Content Planner + Brand Artifacts

> **Read CLAUDE.md first, then this file.** Runs parallel after Agent 1.

## Prerequisites Check

```bash
ls src/data/knowledge-base.ts && ls src/data/personas.ts && ls src/data/voice-guide.ts
ls data/artifacts/knowledge_base/lovable/company_overview/v1.md    # Real KB exists
ls data/artifacts/voice_style_guide/lovable/guide/v1.md            # Voice guide exists
ls data/artifacts/audience_personas/carta/david/v1.md              # Personas exist
npm run dev
```

## Files You Own

```
src/app/(dashboard)/planner/page.tsx
src/app/(dashboard)/planner/_components/
src/app/(dashboard)/artifacts/page.tsx
src/app/(dashboard)/artifacts/_components/
```

## Data Sources — ALL Real

| Data | Source |
|------|--------|
| KB: Company Overview | `data/artifacts/knowledge_base/lovable/company_overview/v1.md` |
| KB: Brand Perception | `data/artifacts/knowledge_base/lovable/brand_perception/v1.md` |
| KB: Competitor Registry | `data/artifacts/knowledge_base/lovable/competitor_registry/v1.md` |
| KB: Customer Reviews | `data/artifacts/knowledge_base/lovable/customer_reviews/v1.md` |
| KB: Weakness Analysis | `data/artifacts/knowledge_base/lovable/weakness_analysis/v1.md` |
| Voice Style Guide | `data/artifacts/voice_style_guide/lovable/guide/v1.md` |
| Personas: Carta | `data/artifacts/audience_personas/carta/*/v1.md` (david v1+v2, elena, lukas, marcus, sarah) |
| Personas: Lovable | `data/artifacts/audience_personas/lovable/*/v1.md` (david, marcus, sarah) |
| Topics (from gap briefs) | `data/artifacts/gap_analysis/lovable/gap_report.md` — top 25 briefs = topics |
| Cluster specs | `data/artifacts/gap_analysis/lovable/generation_spec.md` |
| Topic taxonomy | `data/artifacts/topic_discovery/lovable/taxonomy/*.json` |
| Company context | `data/artifacts/company_context/lovable.md` |

---

## Step 1: Content Planner — Discover Tab

**Topic grid** — responsive 3-4 column card grid. Derive topics from gap_report.md top 25 briefs:

```tsx
function TopicCard({ topic }: { topic: Topic }) {
  return (
    <div
      className="bg-surface border border-border rounded-md p-[14px] hover:border-border-strong cursor-pointer transition-[border-color] duration-150"
      onClick={() => openDetailPanel(topic)}
    >
      <div className="flex justify-between items-start mb-2">
        <h4 className="text-[13px] font-semibold text-text-primary leading-tight line-clamp-2 flex-1 mr-2">
          {topic.title}
        </h4>
        <Badge variant={topic.priority === 'high' ? 'error' : topic.priority === 'medium' ? 'warning' : 'info'}>
          {topic.priority}
        </Badge>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <Badge variant={topic.coverage === 'gap' ? 'error' : topic.coverage === 'partial' ? 'warning' : 'success'}>
          {topic.coverage}
        </Badge>
        <span className="text-[10px] text-text-tertiary">{topic.cluster}</span>
      </div>
      <div className="flex items-center gap-1">
        {topic.personas.map(p => <StatusDot key={p} status="active" />)}
        <span className="text-[10px] text-text-tertiary ml-auto">Gap: {topic.gapScore.toFixed(3)}</span>
      </div>
    </div>
  );
}
```

**Mapping gap briefs to topics:**
- Title = brief title
- Priority: gap > 0.10 = High, > 0.05 = Medium, else Low
- Coverage: significant_gap = "Gap", gap_to_close = "Partial", roughly_equal/company_wins = "Covered"
- Cluster = from brief data

**Click card → detail panel** (360px, slides from right):
- Related queries, exemplar citations, persona breakdown, suggested format
- Mini Plotly scatter (dynamic import, ssr: false, ~200px height) showing cluster neighborhood
- "Add to Cycle" button

**Filters:** Persona, Coverage, Priority, Cluster, Source. Grid/List toggle. Bulk select.

### ✅ Verify Before Proceeding

Visit `/planner`. Grid should show 25+ topic cards with real titles from gap report. Priorities should be color-coded. Click a card — detail panel slides in with real exemplar data. If cards are empty, gap report parser is broken.

---

## Step 2: Content Planner — History Tab

Table of published content (mock 5-8 items). Columns: Title, Publish Date, Citations, Platforms, CPS Predicted vs Actual.

### ✅ Verify: Tab switch works. Table renders with sortable columns.

---

## Step 3: Brand Artifacts — Document Tabs (5 tabs)

**7 total tabs.** First 5 are standard document renderers:

**Layout per document tab:**
```
┌──────────────────────────────────────────────────┐
│ [Section Nav]  (200px, sticky)  │  [Markdown]     │
│                                 │                 │
│  • Executive Summary            │  # Title        │
│  • Market Position              │                 │
│  • Brand Positioning    ← active│  ## Section...  │
│  • Key Differentiators          │  body text...   │
│  • Strengths                    │                 │
│  • Challenges                   │                 │
└──────────────────────────────────────────────────┘
```

**Section nav:** Auto-generate from H2 headings in markdown. Click → smooth scroll. Active section highlighted with `var(--accent)`.

**Markdown rendering:** Use `react-markdown` with `remark-gfm`. Custom components:
```tsx
const markdownComponents = {
  h1: ({ children }) => <h1 className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary mb-4">{children}</h1>,
  h2: ({ children }) => <h2 className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary mt-8 mb-3 pt-6 border-t border-border">{children}</h2>,
  h3: ({ children }) => <h3 className="font-display text-[14px] font-semibold tracking-[-0.01em] text-text-primary mt-4 mb-2">{children}</h3>,
  p: ({ children }) => <p className="text-[14px] text-text-secondary leading-[1.55] mb-3">{children}</p>,
  a: ({ href, children }) => <a href={href} className="text-accent hover:underline">{children}</a>,
  table: ({ children }) => <table className="w-full border-collapse my-4">{children}</table>,
  th: ({ children }) => <th className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary text-left p-[6px_10px] border-b border-border">{children}</th>,
  td: ({ children }) => <td className="text-[12px] p-[6px_10px] border-b border-border-subtle">{children}</td>,
  code: ({ children }) => <code className="font-mono text-[14px] bg-surface border border-border rounded-sm px-1">{children}</code>,
  ul: ({ children }) => <ul className="space-y-1 mb-3 pl-4">{children}</ul>,
  li: ({ children }) => <li className="text-[14px] text-text-secondary leading-[1.55] list-disc">{children}</li>,
};
```

**Load REAL markdown files** — these are full documents (3,000-12,000+ words). "Last Updated" timestamp top-right. Search across document.

### ✅ Verify Before Proceeding

Switch through all 5 document tabs. Each should render thousands of words of real content. Section nav should scroll to correct headings. Company Overview should show Lovable content. Competitor Registry should show detailed competitor analysis. If content is empty, file path or parser is wrong.

---

## Step 4: Voice Style Guide Tab (Special UI)

In addition to rendered markdown:

**Register selector** (segmented control): Tactical | Analytical | Empathy. Shows per-register metrics (sentence length, paragraph length, tone, pace).

**Lexicon browser** (two columns):
- FAVOR: green badges — constraint, validate, compress, mechanism, threshold, handoff, scaffold, surface, traction, sandbox, throughput
- AVOID: red badges — production-ready (unqualified), enterprise-grade, empower, innovative, seamless, leverage, disruptive, game-changer, best-in-class

**Anti-pattern checklist:** 8 items from guide with checkboxes.

**Before/After examples:** 3 collapsible sections. Each: BEFORE (gray bg) + AFTER (accent-subtle bg) + explanation.

### ✅ Verify: Register selector changes metrics. Lexicon shows favor/avoid terms. Before/after examples expand/collapse.

---

## Step 5: Audience Personas Tab

Expandable cards for all personas (Carta: david v1+v2, elena, lukas, marcus, sarah. Lovable: david, marcus, sarah).

Each card: name + title + client badge in header. Click → expands to 7 collapsible sections (Snapshot, Daily Reality, Core Fears, Deep Motivations, Trust Builders, Trust Killers, Pain Points, How We Serve). Edit mode toggle for inline editing.

### ✅ Verify: Cards expand. Sections collapse independently. Real persona content from markdown files.

---

## Step 6: Re-run Pipeline Section

Bottom of artifacts page. "Last full run: March 13, 2026". "Re-run Full Pipeline" button → navigates to `/onboarding`.

---

## Troubleshooting

### Markdown Renders as Raw Text
**Symptom:** Seeing `## Heading` instead of formatted heading.
**Fix:** Ensure you pass content string to `<ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownContent}</ReactMarkdown>`, not as children JSX. The content must be a string.

### Section Nav Links Don't Scroll
**Symptom:** Clicking section name does nothing.
**Fix:** Generate heading IDs from text: `id={heading.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '')}`. Use `document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })`.

### Large Markdown Files Slow to Render
**Symptom:** Persona/KB pages take 2+ seconds to display.
**Fix:** Use `React.memo` on the markdown renderer. For very large docs (competitor_registry is ~12K words), consider lazy-loading sections or virtualizing the content.

### Plotly Mini-Scatter SSR Error in Planner Detail Panel
**Fix:** Same as Agent 3: `dynamic(() => import('react-plotly.js'), { ssr: false })`. Even for a small 200px scatter, this is required.

### Tab State Resets on Navigation
**Symptom:** Switching to another page and back resets active tab.
**Fix:** Store active tab in URL params: `/artifacts?tab=voice-guide`. Read from `useSearchParams()`.

### Persona Edit Mode Changes Not Persisting
**Fix:** For now, store edits in local component state. Show toast "Changes saved locally" on edit. Backend persistence comes later when Aryan connects the API.

---

## Completion Criteria

- [ ] Planner: 25+ real topic cards visible in grid
- [ ] Topic detail panel slides in with real exemplar data
- [ ] Filters work on grid
- [ ] "Add to Cycle" button shows toast
- [ ] History tab: table of published content
- [ ] Artifacts: all 7 tabs render
- [ ] First 5 tabs: REAL markdown content (3,000-12,000+ words)
- [ ] Section nav auto-generates from H2 headings and scrolls
- [ ] Voice Guide: register selector, lexicon browser, anti-patterns, before/after
- [ ] Persona cards expand/collapse with real content
- [ ] Re-run pipeline section at bottom
- [ ] `npx tsc --noEmit` — 0 errors
