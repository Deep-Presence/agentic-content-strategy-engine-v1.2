# CLAUDE.md — Deep Presence Frontend

> **Read this ENTIRE file before writing any code.**
> Then read `/brand-system.md` to understand the visual design system.
> Then read your specific AGENT file for build instructions.

---

## 1. Project Overview

**Deep Presence** is a citation intelligence SaaS platform. It tracks how brands get cited across AI engines (ChatGPT, Claude, Perplexity, Google AI Overview, Gemini) and provides deep analytics, content strategy tools, and competitive intelligence.

This frontend is a **Next.js 14 App Router** application in production-grade development. **This is NOT a prototype or MVP.** Every component, every interaction, and every data display must be production-quality.

**Light mode is the default.**

---

## 2. Tech Stack

| Layer | Technology | Version/Notes |
|-------|-----------|---------------|
| Framework | Next.js 14 | App Router, TypeScript strict |
| Styling | Tailwind CSS | Extended via `theme.config.ts` |
| Components | shadcn/ui | Restyled to brand tokens |
| Charts (standard) | Recharts | Bar, line, area, radar, scatter, composed |
| Charts (embedding) | D3.js | Territory map, force simulations, canvas rendering |
| Charts (embedding alt) | Plotly.js | `react-plotly.js` — always dynamic import with `ssr: false` |
| Drag & Drop | @dnd-kit | `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` |
| Animation | Framer Motion | Page transitions, micro-interactions |
| Date Picker | react-day-picker v9 | Calendar engine for DateRangePicker |
| Date Utils | date-fns v4 | Formatting, preset math (Last 7d, This quarter) |
| Markdown | react-markdown + remark-gfm | Artifact rendering |
| Icons | lucide-react | 24px grid, 1.5px stroke |
| State | Zustand | Sidebar, workspace, theme, notifications |

---

## 3. Brand System — READ FIRST

### ⚠️ MANDATORY: Read `/brand-system.md` Before Writing Any Code

The brand system file is the single source of truth for all visual design decisions. Every agent MUST read it before writing any component, page, or styling. It governs colors, typography, spacing, borders, shadows, and interaction patterns.

### Source Files

| File | Purpose | Read Order |
|------|---------|------------|
| `/brand-system.md` | Human-readable design reference | **READ FIRST** |
| `/src/lib/theme.config.ts` | Machine-consumable tokens. Import from this. | Reference during coding |

### 10 Absolute Rules (Violations = Reject)

1. **NEVER hardcode any color, font, spacing, or radius.** Use `var(--token)` or Tailwind classes from `theme.config.ts`.
2. **Both modes use visible 1px borders on all cards/containers.** No borderless cards.
3. **No glassmorphism on cards.** `backdrop-filter: blur()` only on tooltips.
4. **Dense UI for data elements only.** 30px buttons, 10-11px overline labels, 6px table cell padding. **Navigation and page chrome use 13-14px** — see Section 4.
5. **One typeface for non-code text.** Space Grotesk only. JetBrains Mono for code/data values.
6. **Accent is Teal.** Light: `#5BA4C4`. Dark: `#6CB8D2`. Not indigo. Not purple.
7. **Light grays = Slate-tinted.** Dark grays = pure neutral. This is the Supabase pattern.
8. **No gradients in product UI.** Marketing only.
9. **Shadows minimal.** `--shadow-float` for floating elements only. No shadows on cards.
10. **Max font-weight is 600.** Never use 700/bold in product UI.

### CSS Setup

Light mode is default: `<html>` with no attribute. Dark mode: `<html data-theme="dark">`.

Generate all CSS custom properties in `globals.css` from `theme.config.ts` using `generateCSSVariables('light')` for `:root` and `generateCSSVariables('dark')` for `[data-theme="dark"]`.

---

## 4. Typography Sizing Guide

Dense UI applies to **data-heavy elements only** (table headers, metric overlines, badges, filter chips). Navigation, page titles, body text, and page chrome use comfortable reading sizes.

| Element | Size | Weight | Font |
|---------|------|--------|------|
| Page title | 20px | 600 | Space Grotesk |
| Section heading | 14-16px | 600 | Space Grotesk |
| Sidebar nav items | 13px | 400 normal, 500 active | Space Grotesk |
| Sidebar section headers | 10px uppercase | 600 | Space Grotesk |
| Top bar breadcrumbs | 13px | 400 | Space Grotesk |
| Top bar search text | 13px | 400 | Space Grotesk |
| Body text / descriptions | 13-14px | 400 | Space Grotesk |
| Table headers | 10px uppercase | 600, letter-spacing 0.06em | Space Grotesk |
| Table cell text | 12px | 400 | Space Grotesk |
| Table cell data values | 12px | 500 | JetBrains Mono |
| KPI/metric large value | 22-28px | 600 | JetBrains Mono |
| KPI overline label | 10px uppercase | 600, letter-spacing 0.06em | Space Grotesk |
| Badge text | 9-10px | 600 | Space Grotesk |
| Button text | 12px | 500 | Space Grotesk |
| Drawer title | 16px | 600 | Space Grotesk |
| Drawer body text | 13px | 400 | Space Grotesk |
| Empty state title | 18px | 600 | Space Grotesk |
| Empty state description | 14px | 400 | Space Grotesk |
| Chart axis labels | 10px | 400 | Space Grotesk |
| Chart tooltip text | 11px | 400 | Space Grotesk |
| Trend delta values | 11px | 600 | JetBrains Mono |

**The general principle:** If you're unsure whether something is too small, it probably is. Navigation and readable content should never be below 13px. Only labels, badges, and axis ticks go to 10-11px.

---

## 5. Application Shell

### Sidebar (200px expanded, 52px collapsed)

The sidebar uses grouped sections with colored section headers:

```
[Locus symbol 24px] deep presence (15px, weight 600)
{Workspace Name} ▾ (13px, single dropdown)
─────────────────────────────────────────
Home

PRESENCE                    (muted teal, 10px uppercase)
  Citation intelligence
  Competitive position
  Prompt tracking

SIGNALS                     (muted amber, 10px uppercase)
  Content performance
  Technical readiness
  Embedding lab

CONTENT                     (muted green, 10px uppercase)
  Content planner
  Content studio

KNOWLEDGE                   (muted purple, 10px uppercase)
  Brand hub
─────────────────────────────────────────
Settings
{user avatar + name}                    (bottom-pinned)
```

**Sidebar styling:**
- Background: follows global theme (light/dark), `var(--surface)` or sidebar-specific surface
- Right border: `1px solid var(--border)`
- Nav items: **13px**, padding 6px 12px 6px 16px, row height **34px**
- Active item: `background: var(--accent-subtle); color: var(--text-primary); font-weight: 500`
- Section headers: 10px uppercase, 0.08em letter-spacing, each section has a distinct muted color
- Workspace selector: single dropdown showing workspace name + chevron, 13px
- No collapse arrow next to logo — collapse via sidebar edge hover or keyboard shortcut only
- Locus symbol: 24px. Wordmark "deep presence": 15px, weight 600

### Top Bar (44px)

- Left: breadcrumb trail (13px)
- Right: theme toggle (sun/moon), Cmd+K search (13px), notification bell, user avatar (28px)
- Border bottom: `1px solid var(--border)`

### Layouts

- Auth routes (`/login`, `/register`, `/join`): separate layout, no sidebar
- Onboarding (`/onboarding`): separate layout, no sidebar
- All other routes: dashboard layout with sidebar + top bar

---

## 6. Routes

| Route | Page | Agent File |
|-------|------|-----------|
| `/login` | Email + password | AGENT-2 |
| `/register` | Company registration | AGENT-2 |
| `/join` | Invite code join | AGENT-2 |
| `/onboarding` | Pipeline run (4 screens) | AGENT-2 |
| `/` | Home command center | AGENT-2 |
| `/analytics` | Citation Intelligence (primary analytics) | AGENT-3 |
| `/competitive-position` | Competitive Position | AGENT-COMPETITIVE-POSITION |
| `/prompt-tracking` | Prompt Tracking | AGENT-PROMPT-TRACKING |
| `/content-performance` | Content Performance | AGENT-CONTENT-PERFORMANCE |
| `/technical-readiness` | Technical Readiness | AGENT-TECHNICAL-READINESS |
| `/embedding-lab` | Deep Embedding Lab (D3 territory map, scatter, analysis) | Embedding Lab agent |
| `/planner` | Content Planner | AGENT-5 |
| `/content` | Content Studio (Kanban + Editor) | AGENT-4 |
| `/artifacts` | Brand Hub (KB, Voice Guide, Personas, Gap Intel, Site Health) | Brand Hub agent |
| `/settings` | Settings (5 tabs) | AGENT-6 |

**Page specs live in each agent's file. Not here.** Read your AGENT file for full build details.

---

## 7. Real Data — Pipeline Artifacts

### Location

`/data/artifacts/` — symlinked to `../../result-draft/artifacts/`.

### Key Data Files

| Data | Source Path | Used By |
|------|-----------|---------|
| Gap analysis (99 queries, gaps, clusters) | `gap_analysis/lovable/gap_report.md`, `generation_spec.md` | Citation Intel, Competitive, Embedding Lab |
| Gap analysis complete JSON | `gap_analysis/lovable/gap_analysis_complete.json` | Multiple pages |
| Enriched citations (structural signals) | `gap_analysis/lovable/enriched_citations.json` | Content Performance, Embedding Lab |
| Embedding projections | `gap_analysis/lovable/visualizations/embedding_projections_*.json` | Embedding Lab |
| Company embeddings | `gap_analysis/lovable/company_embeddings.json` | Embedding Lab |
| Site audit reports | `site_audit/lovable/*/report.md` | Technical Readiness |
| Platform results | `gap_analysis/lovable/platform_results/*.jsonl` | Prompt Tracking, Citation Intel |
| Content pipeline | `content/carta/content/brief-001/`, `brief-002/` | Content Studio |
| Knowledge base docs | `knowledge_base/lovable/*/v1.md` | Brand Hub |
| Voice style guide | `voice_style_guide/lovable/guide/v1.md` | Brand Hub |
| Audience personas | `audience_personas/lovable/*/v1.md` | Brand Hub |
| Topic discovery | `topic_discovery/lovable/taxonomy/*.json` | Content Planner |

**For pages that need time-series or daily data not available in the pipeline artifacts, use realistic mock data that matches the backend API schema exactly.** Structure mock data so Aryan can swap in real API endpoints without restructuring components.

---

## 8. CRITICAL: Real Brand Logos Everywhere

### ⚠️ NO CARTOONISH LOGOS. NO COLORED CIRCLES WITH INITIALS. NO PLACEHOLDER ICONS.

Every brand, competitor, and platform that appears ANYWHERE in the application must display its **real logo** fetched from the actual website. This is a production-grade platform — placeholder logos make it look like a toy.

### Logo Fetching Priority Chain

```
1. Google Favicon API (most reliable):
   https://www.google.com/s2/favicons?domain={domain}&sz=32

2. Clearbit Logo API (higher quality, may have CORS issues):
   https://logo.clearbit.com/{domain}

3. Logo.dev API:
   https://img.logo.dev/{domain}?token=pk_...

4. LAST RESORT ONLY — text initials in a colored circle
   (only if ALL API calls fail)
```

### Implementation

Every agent should use or create a `BrandLogo` component:

```tsx
function BrandLogo({ domain, size = 20, className }: { domain: string; size?: number; className?: string }) {
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt={domain}
      width={size}
      height={size}
      className={className}
      style={{ borderRadius: 4 }}
      onError={(e) => {
        const target = e.target as HTMLImageElement;
        if (!target.dataset.fallback) {
          target.dataset.fallback = '1';
          target.src = `https://logo.clearbit.com/${domain}`;
        }
      }}
    />
  );
}
```

**DO NOT use `crossOrigin="anonymous"` on logo images** — it causes CORS failures with Clearbit and other providers.

### Where Real Logos Must Appear

- **AI Platform logos**: ChatGPT (openai.com), Claude (anthropic.com), Perplexity (perplexity.ai), Google AI (google.com), Gemini (gemini.google.com)
- **Competitor logos**: bolt.new, cursor.com, replit.com, v0.dev, emergent.sh, snyk.io, etc.
- **Cited URL domains**: Any domain that appears as a citation source
- **Brand self-logo**: lovable.dev (with a distinguishing teal ring/border)
- **Platform preference sections**: When showing "ChatGPT prefers X", the ChatGPT logo must be real
- **Answer history**: Platform logos next to each AI response
- **Drift tracker**: Competitor logos showing who took your citation

**If a component shows a brand name, it MUST show the real logo next to it.**

---

## 9. Global Filter Bar Pattern

Every analytics page (Citation Intelligence, Competitive Position, Content Performance, Technical Readiness, Prompt Tracking) must have a **global filter bar** below the page title.

### Filter Bar Layout

```
📅 Mar 1, 2026 – Mar 28, 2026  |  {page-specific filters}  |  × Clear Filters
```

### Date Picker Requirements

- **Use the shared `DateRangePicker` component** from `@/components/ui`
- Two-month calendar view side by side (react-day-picker v9)
- User clicks start date, then end date, range highlights between them
- Presets sidebar (Last 7d, 30d, 90d, This month, This quarter) — customizable via `presets` prop, or pass `presets={[]}` to hide
- **NO region filter** — not supported in pipeline yet
- All charts on the page respond to the selected date range
- Every chart shows **daily data points** within the selected range (not weekly aggregation)

### Page-Specific Filters

| Page | Additional Filters |
|------|-------------------|
| Citation Intelligence | Cluster, Platform |
| Competitive Position | Cluster, Platform |
| Content Performance | Cluster, Lifecycle Stage |
| Technical Readiness | Severity, Dimension |
| Prompt Tracking | Topic |

### Filter State

Store filter state in component-level `useState` or a shared Zustand store if one exists (`useFilterStore`). When the user changes filters on one page and navigates to another, filters can reset — cross-page persistence is not required for v1.

---

## 10. Side Drawer Pattern

Every page with data tables uses a **50% viewport width side drawer** that slides from the right when a row is clicked.

### Drawer Specifications

- Width: 50% of viewport
- Slides from right with Framer Motion or CSS transition
- Close button (×) in top-right corner
- Escape key closes drawer
- Background table/content stays visible but dimmed (semi-transparent overlay)
- Drawer has its own scroll context
- Drawer header: title + metadata
- Drawer content: composable — each page passes different sections

### Drawer Styling

```
- Background: var(--surface)
- Left border: 1px solid var(--border)
- Shadow: var(--shadow-float) — this is the ONE place shadows are allowed
- Header padding: 20px 24px
- Content padding: 0 24px 24px
- Close button: 30px, ghost variant
```

### Pages That Use Drawers

| Page | Drawer Trigger | Drawer Content |
|------|---------------|----------------|
| Citation Intelligence | Click citation URL row | All prompts citing this URL |
| Competitive Position | Click competitor OR query | Competitor detail OR gap analysis |
| Prompt Tracking | Click prompt row | Mention rates, answer history, query fanouts |
| Content Performance | Click content piece | 7-section deep dive |
| Technical Readiness | Click finding row | Affected pages, fix instructions, impact estimate |

---

## 11. Shared Component Library

All components in `/src/components/ui/`. Export from `/src/components/ui/index.ts`.

### Core Components (built by Agent 1)

Button, Input, Card, MetricCard, KPIRow, Badge, StatusDot, Table, Sidebar, TopBar, TabBar, FilterBar, Modal, Dropdown, SearchCommand, EmptyState, Avatar, ProgressBar, Toggle, Skeleton, Toast, ScoreGauge, Sparkline, LocusLogo, WorkspaceSelector

### Additional Shared Components (built and available)

- `DateRangePicker` — Two-month calendar with presets (react-day-picker v9 + date-fns). Props: `value`, `onChange`, `presets`, `minDate`, `maxDate`. Re-exports `DateRange` type.
- `BrandLogo` — Real favicon fetcher with fallback chain: Google Favicon → Clearbit → Logo.dev → text initials. Props: `domain`, `size`, `fallbackText`. No `crossOrigin` (avoids CORS). See Section 8.
- `SlideDrawer` — 50vw right-side drawer (Framer Motion). Props: `open`, `onClose`, `title`, `subtitle`, `width`. Escape to close, body scroll lock, semi-transparent overlay. See Section 10.
- `GapBadge` — Semantic color-coded gap severity badge (build when first page needs it)
- `ShareOfVoiceBar` — Animated SOV progress bar (build when first page needs it)

**If a component you need already exists in `_components/` of another page, check if it should be promoted to shared. But never modify another agent's files — create your own version if needed.**

### Component Pattern

Every component must:
- Use CSS variable-based Tailwind classes (never hardcoded hex)
- Have a TypeScript props interface
- Follow the typography sizing guide (Section 4)
- Have visible 1px borders on any card/container element
- Support both light and dark mode through CSS variables

---

## 12. TypeScript Types

Types are in `/src/types/index.ts` (created by Agent 1).

Key types: `Query`, `Cluster`, `SiteAudit`, `ContentBrief`, `ContentPiece`, `Persona`, `KBDocument`, `VoiceGuide`, `Topic`, `EmbeddingPoint`, `Platform`, `Notification`.

All 5 AI platforms: `type Platform = 'chatgpt' | 'claude' | 'perplexity' | 'google_ai_overview' | 'gemini'`

If your page needs additional types not in `index.ts`, create them in your page's `_components/` directory. Do not modify the shared types file.

---

## 13. File Ownership Rules

1. Shared UI components (`/src/components/ui/`) — import only, never modify unless you are the sidebar/foundation agent.
2. Each agent owns their route directories exclusively.
3. New components go in the agent's private `_components/` dir, not shared.
4. All shared imports: `import { Button, Card } from '@/components/ui'`
5. If you need a component another agent built, create your own version — do not import from another page's `_components/`.

---

## 14. Verification Protocol

Every agent must verify at each major step before proceeding.

| Check | Command | Expected |
|-------|---------|----------|
| Dev server starts | `npm run dev` | No errors, page loads |
| TypeScript compiles | `npx tsc --noEmit` | 0 errors |
| Build succeeds | `npm run build` | No build errors |
| Route renders | Visit route in browser | Content visible, no blank page |
| Styles correct | Visual check | Correct colors, borders, sizing |
| Dark mode works | Toggle theme | Proper dark mode styling |
| Logos load | Visual check | Real favicons, not placeholders |

**After each major build step, run `npm run dev` and visually check.**

---

## 15. Troubleshooting

### Plotly.js SSR Error
**Symptom:** `window is not defined`
**Fix:** Always dynamic import: `const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });`

### Brand Logos Not Loading (CORS)
**Symptom:** Broken image icons where logos should be.
**Fix:** Do NOT use `crossOrigin="anonymous"` on `<img>` tags for external logos. Use Google Favicon API as primary source. Add fallback chain in `onError`.

### Tailwind Classes Not Applying
**Fix:** Check `tailwind.config.ts` content array includes `'./src/**/*.{js,ts,jsx,tsx,mdx}'`.

### CSS Variables Undefined
**Fix:** Check `globals.css` is imported in `layout.tsx`. Check variable name matches exactly.

### Recharts Colors
**Fix:** Recharts accepts CSS variable strings directly: `stroke="var(--accent)"`, `fill="var(--success)"`. No need for a `useThemeColors()` hook. Exception: HTML5 Canvas (used in D3 scatter) requires resolved hex values — only use `useThemeColors()` for Canvas contexts.

### Import Path Errors
**Fix:** Verify `src/components/ui/index.ts` exists. Check `tsconfig.json` has `"@/*": ["./src/*"]`.

### Text Too Small
**Symptom:** Nav items, breadcrumbs, or body text feel cramped and hard to read.
**Fix:** Reference the Typography Sizing Guide (Section 4). Navigation = 13px. Body text = 13-14px. Only labels and badges go below 12px.

---

## 16. Brand Application Checklist

Run this before declaring any page complete:

- [ ] No hardcoded hex colors — all from CSS variables
- [ ] All cards/containers have `1px solid var(--border)`
- [ ] Buttons are 30px default height
- [ ] Overline labels: 10px uppercase, letter-spacing 0.06em
- [ ] Table headers: 10px uppercase, `var(--text-tertiary)`
- [ ] Table cells: 6px vertical padding
- [ ] Nav items: 13px (NOT 10-11px)
- [ ] Page titles: 20px
- [ ] Body text: 13-14px
- [ ] Data values: JetBrains Mono
- [ ] All other text: Space Grotesk
- [ ] No font-weight above 600
- [ ] No shadows on cards
- [ ] No gradients in product UI
- [ ] **ALL brand logos are real** — fetched via favicon/Clearbit API
- [ ] **NO cartoonish or placeholder logos anywhere**
- [ ] **NO colored circles with initials** for any brand that has a website
- [ ] Platform logos (ChatGPT, Claude, Perplexity, Google AI, Gemini) are real favicons
- [ ] Competitor logos are real favicons
- [ ] Global filter bar present with calendar date picker
- [ ] Side drawer (50% width) works on table row clicks
- [ ] Light mode default, correct styling
- [ ] Dark mode toggle works, correct styling
- [ ] Hover states use `--border-strong`
- [ ] Active nav: `--accent-subtle` bg + `--text-primary` text