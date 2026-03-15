# CLAUDE.md — Deep Presence Frontend

> **Read this ENTIRE file before writing any code.**
> Every agent reads this first, then reads their specific AGENT-N file.

---

## 1. Project Overview

**Deep Presence** is a citation intelligence and revenue attribution SaaS platform.
It tracks how brands get cited across AI engines (ChatGPT, Claude, Perplexity, Google AI Overview, Gemini) and connects those citations to revenue.

This frontend is a **Next.js 14 App Router** application. **Light mode is the default.**

---

## 2. Tech Stack

| Layer | Technology | Version/Notes |
|-------|-----------|---------------|
| Framework | Next.js 14 | App Router, TypeScript strict |
| Styling | Tailwind CSS | Extended via `theme.config.ts` |
| Components | shadcn/ui | Restyled to brand tokens |
| Charts (standard) | Recharts | Bar, line, area, radar |
| Charts (embedding) | Plotly.js | `react-plotly.js` — always dynamic import with `ssr: false` |
| Drag & Drop | @dnd-kit | `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` |
| Animation | Framer Motion | Page transitions, micro-interactions |
| Markdown | react-markdown + remark-gfm | Artifact rendering |
| Icons | lucide-react | 24px grid, 1.5px stroke |
| State | Zustand | Sidebar, workspace, theme, notifications |

---

## 3. Brand System — CRITICAL RULES

### Source Files

| File | Purpose |
|------|---------|
| `/brand-system.md` | Human-readable design reference. Read first. |
| `/src/lib/theme.config.ts` | Machine-consumable tokens. Import from this. |

### 10 Absolute Rules (Violations = Reject)

1. **NEVER hardcode any color, font, spacing, or radius.** Use `var(--token)` or Tailwind classes from `theme.config.ts`.
2. **Both modes use visible 1px borders on all cards/containers.** No borderless cards.
3. **No glassmorphism on cards.** `backdrop-filter: blur()` only on tooltips.
4. **Dense UI.** 30px buttons, 10-11px labels, 6px table cell padding.
5. **One typeface for non-code text.** Space Grotesk only. JetBrains Mono for code/data.
6. **Accent is Teal.** Light: `#5BA4C4`. Dark: `#6CB8D2`. Not indigo. Not purple.
7. **Light grays = Slate-tinted.** Dark grays = pure neutral. This is the Supabase pattern.
8. **No gradients in product UI.** Marketing only.
9. **Shadows minimal.** `--shadow-float` for floating elements only. No shadows on cards.
10. **Max font-weight is 600.** Never use 700/bold in product UI.

### CSS Setup

Light mode is default: `<html>` with no attribute. Dark mode: `<html data-theme="dark">`.

Generate all CSS custom properties in `globals.css` from `theme.config.ts` using `generateCSSVariables('light')` for `:root` and `generateCSSVariables('dark')` for `[data-theme="dark"]`.

---

## 4. Real Data — Pipeline Artifacts

### Location

`/data/artifacts/` — symlinked to `../../result-draft/artifacts/`.

**All LFS JSON files are available locally. Import directly. Never generate fake or synthetic data.**

### Key Files by Agent

| Agent | Key Files |
|-------|----------|
| 3 (Analytics) | `gap_analysis/lovable/gap_report.md`, `generation_spec.md`, `visualizations/embedding_projections_*.json`, `site_audit/lovable/*/report.md` |
| 4 (Content) | `content/carta/content/brief-001/`, `brief-002/` (full pipeline: outline→draft→enriched→final→formatted) |
| 5 (Artifacts) | `knowledge_base/lovable/*/v1.md`, `voice_style_guide/lovable/guide/v1.md`, `audience_personas/*/v1.md` |

See each agent's AGENT-N file for complete data source tables.

---

## 5. Application Shell

### Sidebar (200px expanded, 52px collapsed)

```
[Workspace Selector: Company ▾ / Project ▾]
────────────────────────────────────────────
● Home
● Analytics
  └─ Deep Embedding Lab
● Content Studio
● Content Planner
● Brand Artifacts
● Attribution
────────────────────────────────────────────
⚙ Settings                          (bottom)
```

- Background: `var(--surface)`, right border: `1px solid var(--border)`
- Nav items: 11px, padding 5px 8px
- Active: `background: var(--accent-subtle); color: var(--accent);`
- Locus compact lockup at top (16px symbol + 12px text)

### Top Bar (44px)

- Left: breadcrumb trail
- Right: Cmd+K search, notification bell (badge count), user avatar
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
| `/analytics` | 5-tab measurement dashboard | AGENT-3 |
| `/analytics/lab` | Deep Embedding Lab (4 views) | AGENT-3 |
| `/content` | Content Studio (Kanban + Editor) | AGENT-4 |
| `/planner` | Content Planner | AGENT-5 |
| `/artifacts` | Brand Artifacts (7 tabs) | AGENT-5 |
| `/attribution` | Attribution Dashboard | AGENT-6 |
| `/settings` | Settings (5 tabs) | AGENT-6 |

**Page specs live in each agent's file. Not here.** Read your AGENT-N file for full build details.

---

## 7. Shared Component Library (Agent 1 builds all)

All components in `/src/components/ui/`. Export from `/src/components/ui/index.ts`.

### Required Components (25)

Button, Input, Card, MetricCard, KPIRow, Badge, StatusDot, Table, Sidebar, TopBar, TabBar, FilterBar, Modal, Dropdown, SearchCommand, EmptyState, Avatar, ProgressBar, Toggle, Skeleton, Toast, ScoreGauge, Sparkline, LocusLogo, WorkspaceSelector

### Example: What a Correct Component Looks Like

```tsx
// src/components/ui/Button.tsx
import { cn } from '@/lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'default' | 'lg';
}

export function Button({ variant = 'primary', size = 'default', className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-body font-medium transition-all',
        'duration-[120ms] ease-out cursor-pointer',
        // Size — dense UI: 30px default
        size === 'sm' && 'h-[26px] px-2 text-[11px]',
        size === 'default' && 'h-[30px] px-3 text-[12px]',
        size === 'lg' && 'h-[34px] px-4 text-[13px]',
        // Variant
        variant === 'primary' && 'bg-accent text-text-on-accent rounded-sm hover:bg-accent-hover',
        variant === 'secondary' && 'bg-transparent text-text-primary border border-border rounded-sm hover:border-border-strong hover:bg-surface',
        variant === 'ghost' && 'bg-transparent text-text-secondary rounded-sm hover:bg-surface hover:text-text-primary',
        variant === 'destructive' && 'bg-error text-white rounded-sm',
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
```

### Example: What a Correct Card Looks Like

```tsx
// src/components/ui/Card.tsx
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  hoverable?: boolean;
}

export function Card({ selected, hoverable = true, className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'bg-surface border border-border rounded-md p-[14px] transition-[border-color] duration-150 ease-out',
        hoverable && 'hover:border-border-strong',
        selected && 'border-accent bg-accent-subtle',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
```

**Every component follows this pattern:** CSS variables via Tailwind classes, TypeScript props, dense sizing, visible borders.

---

## 8. TypeScript Types (Agent 1)

Create `/src/types/index.ts`. Full type definitions are in AGENT-1-FOUNDATION.md.

Key types: `Query`, `Cluster`, `SiteAudit`, `ContentBrief`, `ContentPiece`, `Persona`, `KBDocument`, `VoiceGuide`, `Topic`, `EmbeddingPoint`, `Platform`, `Notification`.

All 5 AI platforms: `type Platform = 'chatgpt' | 'claude' | 'perplexity' | 'google_ai_overview' | 'gemini'`

---

## 9. Agent Assignments

| Agent | Scope | File | Runs |
|-------|-------|------|------|
| **1 — Foundation** | Scaffold, components, shell, types, data layer | AGENT-1-FOUNDATION.md | FIRST, solo |
| **2 — Auth+Onboarding+Home** | Login, Register, Join, Onboarding, Home | AGENT-2-AUTH-ONBOARDING-HOME.md | Parallel |
| **3 — Analytics+Lab** | 5-tab Analytics, 4-view Embedding Lab | AGENT-3-ANALYTICS-LAB.md | Parallel |
| **4 — Content Studio** | Kanban, Editor, Scoring, HITL | AGENT-4-CONTENT-STUDIO.md | Parallel |
| **5 — Planner+Artifacts** | Topic grid, KB docs, Voice Guide, Personas | AGENT-5-PLANNER-ARTIFACTS.md | Parallel |
| **6 — Attribution+Settings** | Funnel, ROI, Settings tabs | AGENT-6-ATTRIBUTION-SETTINGS.md | Parallel |

### Execution Timeline

```
Hour 0-3:    Agent 1 alone
Hour 3-8:    Agents 2-6 in parallel (5 simultaneous)
Hour 8-9:    Integration pass
```

---

## 10. File Ownership Rules

1. Agent 1's files are shared infrastructure. Other agents **import only, never modify**.
2. Each agent owns their route directories exclusively.
3. New components go in agent's private `_components/` dir, not shared.
4. All shared imports: `import { Button, Card } from '@/components/ui'`

---

## 11. Verification Protocol

Every agent must verify at each major step before proceeding to the next.

**How to verify:** Run the check. If it fails, fix it before moving on. Do not skip.

| Check | Command | Expected |
|-------|---------|----------|
| Dev server starts | `npm run dev` | No errors, page loads at localhost:3000 |
| TypeScript compiles | `npx tsc --noEmit` | 0 errors |
| Build succeeds | `npm run build` | No build errors |
| Route renders | Visit route in browser | Content visible, no blank page |
| Styles correct | Visual check | Light mode Slate grays, teal accent, visible borders |
| Dark mode works | Toggle theme | Pure neutral grays, lighter teal accent |

**After each major build step, run `npm run dev` and visually check.** Do not batch 5 steps and hope they all work.

---

## 12. Troubleshooting (Common Cross-Agent Issues)

### Plotly.js SSR Error
**Symptom:** `window is not defined` or `document is not defined`
**Cause:** Plotly accesses browser APIs during server-side render.
**Fix:** Always dynamic import:
```tsx
import dynamic from 'next/dynamic';
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });
```

### Tailwind Classes Not Applying
**Symptom:** Colors/spacing wrong despite correct class names.
**Cause:** Tailwind purged the class because content path doesn't include your files.
**Fix:** Check `tailwind.config.ts` content array includes `'./src/**/*.{js,ts,jsx,tsx,mdx}'`.

### CSS Variables Undefined
**Symptom:** Elements show default browser styling or transparent.
**Cause:** `globals.css` not loaded or variables misspelled.
**Fix:** Check `globals.css` is imported in `layout.tsx`. Check variable name matches exactly (e.g., `--border` not `--border-color`).

### Import Path Errors
**Symptom:** `Module not found: Can't resolve '@/components/ui'`
**Cause:** Agent 1 hasn't created the barrel export yet, or `tsconfig.json` paths are wrong.
**Fix:** Verify `src/components/ui/index.ts` exists and exports the component. Check `tsconfig.json` has `"@/*": ["./src/*"]`.

### Data File Import Fails
**Symptom:** `Error: Cannot find module '/data/artifacts/...'`
**Cause:** Symlink not set up, or path is wrong.
**Fix:** Run `ls data/artifacts/` from `frontend/`. If empty, recreate symlink: `ln -s ../../result-draft/artifacts data/artifacts`.

### Framer Motion Layout Shift
**Symptom:** Page content jumps when animations run.
**Cause:** `AnimatePresence` wrapping layout components without `mode="wait"`.
**Fix:** Add `mode="wait"` to `AnimatePresence` and use `layout` prop carefully.

### shadcn/ui Overriding Brand Tokens
**Symptom:** Components have default shadcn colors instead of brand teal.
**Cause:** shadcn generates its own CSS variables that conflict.
**Fix:** After `shadcn init`, replace all shadcn CSS variables in `globals.css` with the brand tokens from `theme.config.ts`. shadcn's variables must be fully replaced, not layered on top.

---

## 13. Brand Application Checklist

Run this before declaring any page complete:

- [ ] No hardcoded hex colors — all from CSS variables
- [ ] All cards/containers have `1px solid var(--border)` — no borderless cards
- [ ] Buttons are 30px default height
- [ ] Labels/overlines: 10-11px, uppercase, letter-spacing 0.06em
- [ ] Table headers: 10px, uppercase, `var(--text-tertiary)`
- [ ] Table cells: 6px vertical padding
- [ ] Fonts: Space Grotesk only (except code = JetBrains Mono)
- [ ] No font-weight above 600
- [ ] No shadows on cards
- [ ] No gradients in product UI
- [ ] Light mode default, looks correct
- [ ] Dark mode toggle works, looks correct
- [ ] Hover states use `--border-strong`
- [ ] Focus states use `--accent` border + `--accent-subtle` ring
- [ ] Active nav: `--accent-subtle` bg + `--accent` text
- [ ] Locus logo uses `currentColor`

---

## 14. Integration Checklist (Post-Build)

After all 6 agents complete:

- [ ] All 12 routes render without errors
- [ ] Sidebar navigation works for all routes
- [ ] Dark/light mode toggle works globally
- [ ] Workspace selector appears on all dashboard pages
- [ ] Top bar breadcrumbs update per route
- [ ] No duplicate component definitions
- [ ] All shared component imports resolve
- [ ] Plotly renders without SSR errors
- [ ] @dnd-kit drag-and-drop works
- [ ] Real artifact data displays correctly
- [ ] Empty states show when data is absent
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds