# Agent 1 — Foundation

> **Read CLAUDE.md first, then this file.** You run FIRST and ALONE. Nothing else starts until you finish.

## Your Mission

Build the skeleton every other agent plugs into: project scaffolding, brand theme integration, 25 shared components, app shell with sidebar, all route stubs, TypeScript types, Zustand stores, and data layer parsing real pipeline artifacts.

---

## Step 1: Scaffold Next.js

```bash
npx create-next-app@14 . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
```

### ✅ Verify Before Proceeding

```bash
npm run dev
```

Open `http://localhost:3000`. You should see the Next.js default page. If not, fix the scaffold before continuing.

---

## Step 2: Install Dependencies

```bash
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
npm install framer-motion recharts plotly.js react-plotly.js
npm install react-markdown remark-gfm
npm install lucide-react zustand
npx shadcn-ui@latest init
```

shadcn config: Style=Default, Base color=Slate, CSS variables=Yes.

### ✅ Verify Before Proceeding

```bash
npm run dev
```

Should still start without errors. If shadcn init broke something, fix it now.

---

## Step 3: Theme Integration

1. Move `Theme.config.ts` to `src/lib/theme.config.ts` (lowercase):
   ```bash
   mv Theme.config.ts src/lib/theme.config.ts
   ```

2. Update `tailwind.config.ts`:
   ```typescript
   import type { Config } from 'tailwindcss';
   import { getTailwindExtend } from './src/lib/theme.config';

   const config: Config = {
     content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
     theme: { extend: getTailwindExtend() },
     plugins: [],
   };
   export default config;
   ```

3. Replace ALL of `src/app/globals.css` with brand CSS variables. **Critical:** After shadcn init, shadcn writes its own CSS variables. You must REPLACE them entirely — not layer on top. The full `:root` and `[data-theme="dark"]` blocks are in the theme.config.ts file's `generateCSSVariables()` output. Write them all out explicitly.

   Light mode values (`:root`):
   ```
   --bg: #F8F9FA; --surface: #FBFCFD; --surface-raised: #FFFFFF; --accent: #5BA4C4; etc.
   ```
   Dark mode values (`[data-theme="dark"]`):
   ```
   --bg: #171717; --surface: #1F1F1F; --surface-raised: #292929; --accent: #6CB8D2; etc.
   ```
   See theme.config.ts for complete list.

4. Add Google Fonts in `src/app/layout.tsx` `<head>`:
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
   ```

5. Light mode default: `<html>` with no `data-theme`. Dark mode: `<html data-theme="dark">`.

### ✅ Verify Before Proceeding

```bash
npm run dev
```

Open browser. The page background should be `#F8F9FA` (very light blue-gray), NOT white and NOT dark. Text should be near-black `#11181C`. If you see shadcn's default zinc palette, the CSS variable replacement failed — go back and fix `globals.css`.

---

## Step 4: Create TypeScript Types

Create `src/types/index.ts` with all data model types:

```typescript
// === Core Entities ===
export interface Company { id: string; name: string; domain: string; createdAt: string; }
export interface User { id: string; name: string; email: string; role: 'admin' | 'editor' | 'viewer'; avatarUrl?: string; }
export interface Workspace { company: Company; projects: Project[]; }
export interface Project { id: string; name: string; domain: string; }

// === 5 AI Platforms (used everywhere) ===
export type Platform = 'chatgpt' | 'claude' | 'perplexity' | 'google_ai_overview' | 'gemini';

// === Gap Analysis ===
export interface Query {
  id: string;
  text: string;
  cluster: string;
  classification: 'significant_gap' | 'gap_to_close' | 'roughly_equal' | 'company_wins';
  gap: number;
  avgCitationSimilarity: number;
  bestCompanyUnit: { id: string; url: string; similarity: number; snippet: string; };
  citedExemplars: CitedExemplar[];
  companyCited: boolean;
  platforms: Platform[];
}
export interface CitedExemplar {
  url: string; domain: string; similarity: number; snippet: string; structure: PageStructure;
}
export interface PageStructure {
  words: number; paragraphs: number; headers: number; lists: number; stats: number; citations: number; readingLevel?: number;
}
export interface GapReport {
  summary: { spaScore: number; meanCitationSimilarity: number; meanCompanySimilarity: number; totalQueries: number; totalCitations: number; averageGap: number; };
  queries: Query[];
  clusters: Cluster[];
}
export interface Cluster {
  id: string; name: string; queryCount: number; citationsAnalyzed: number; requiredElements: string[];
  avgWordCount: number; faqRate: number; tableRate: number; dominantContentType: string; dominantAuthority: string;
}

// === Site Audit ===
export interface SiteAudit {
  overallScore: number; grade: string; pagesCrawled: number; totalFindings: number;
  dimensions: AuditDimension[]; botAccess: { bot: string; allowed: boolean; }[];
  aeoReadiness: { avgSnippetReadiness: number; pagesWithStructuredData: number; avgQuestionHeadingRatio: number; };
  findings: AuditFinding[];
}
export interface AuditDimension { name: string; score: number; weight: number; weighted: number; findings: number; }
export interface AuditFinding { severity: 'critical' | 'high' | 'medium' | 'low'; dimension: string; title: string; affectedPages: number; recommendation: string; }

// === Content Pipeline ===
export interface ContentBrief {
  id: string; title: string; targetCluster: string; targetQuery: string;
  stage: 'triage' | 'brief' | 'generating' | 'review' | 'approved' | 'published';
  personas: string[]; cpsPredict: Record<Platform, number>; cpsActual?: Record<Platform, number>;
  structuralTargets: PageStructure; createdAt: string; publishedAt?: string; publishedUrl?: string;
}
export interface ContentPiece {
  briefId: string; stage: 'outline' | 'draft' | 'enriched' | 'final' | 'formatted';
  markdown: string; wordCount: number; structuralAnalysis: PageStructure;
  voiceComplianceScore: number; interlinkSuggestions: { url: string; anchorText: string; applied: boolean; }[];
}
export interface ContentCycle { id: string; name: string; items: ContentBrief[]; startDate: string; endDate: string; }

// === Knowledge Base, Voice Guide, Personas ===
export interface Persona {
  id: string; name: string; title: string; client: string; version: string;
  sections: { title: string; content: string; }[];
}
export interface KBDocument {
  id: string; type: 'company_overview' | 'brand_perception' | 'competitor_registry' | 'customer_reviews' | 'weakness_analysis';
  client: string; version: string; markdown: string; lastUpdated: string; wordCount: number;
}
export interface VoiceGuide {
  identity: string; registers: VoiceRegister[];
  styleMetrics: Record<string, { default: string; tactical: string; analytical: string; }>;
  lexicon: { favor: LexiconItem[]; avoid: LexiconItem[]; }; antiPatterns: string[];
  workedExamples: { title: string; before: string; after: string; explanation: string; }[];
}
export interface VoiceRegister { name: 'tactical' | 'analytical' | 'empathy'; sentenceLength: string; paragraphLength: string; tone: string; pace: string; }
export interface LexiconItem { term: string; usage: string; frequency: string; }

// === Topics ===
export interface Topic {
  id: string; title: string; priority: 'high' | 'medium' | 'low'; personas: string[];
  coverage: 'covered' | 'gap' | 'partial'; cluster: string; subtopics: string[]; gapScore: number; sources: string[];
}

// === Attribution (demo) ===
export interface AttributionMetrics { aiSourcedTraffic: number; demoRequests: number; pipelineGenerated: number; revenueAttributed: number; }
export interface AttributionFunnelStep { name: string; count: number; conversionRate: number; }
export interface ContentROI { title: string; citationsEarned: number; aiReferredSessions: number; conversions: number; revenue: number; cpsPredicted: number; cpsActual: number; }

// === Embedding Space ===
export interface EmbeddingPoint { id: string; type: 'company' | 'citation' | 'query'; x: number; y: number; cluster: string; label: string; url?: string; similarity?: number; }

// === Notifications ===
export interface Notification {
  id: string; type: 'pipeline_complete' | 'hitl_ready' | 'content_published' | 'citation_gained' | 'system_alert';
  title: string; message: string; read: boolean; createdAt: string; actionUrl?: string;
}

// === Settings ===
export interface TeamMember { id: string; name: string; email: string; role: 'admin' | 'editor' | 'viewer'; status: 'active' | 'invited'; }
export interface ModelConfig { agentType: string; provider: string; model: string; apiKeySet: boolean; }
export interface Integration { id: string; type: 'cms' | 'crm' | 'analytics'; name: string; connected: boolean; lastSync?: string; }
```

### ✅ Verify Before Proceeding

```bash
npx tsc --noEmit
```

0 errors. If type errors exist, fix them now.

---

## Step 5: Build Shared Component Library (25 components)

Create each component in `src/components/ui/`. Then create `src/components/ui/index.ts` that re-exports all of them.

**Every component must:**
- Use CSS variable-based Tailwind classes (never hardcoded hex)
- Have a TypeScript props interface
- Follow dense UI spec (30px heights, 10-11px labels, 6px table padding)
- Have visible 1px borders on any card/container element

See CLAUDE.md Section 7 for Button and Card examples showing the exact pattern.

**Components to build:**

| Component | Key Behavior |
|-----------|-------------|
| `Button` | 4 variants, 3 sizes, 30px default |
| `Input` | 30px height, focus ring with accent |
| `Card` | Always `border border-border`, hover changes border |
| `MetricCard` | Overline label (10px uppercase) + large value + delta |
| `KPIRow` | Grid with hairline separators via 1px gap + bg color trick |
| `Badge` | 5 variants (success/warning/error/info/neutral), pill shape |
| `StatusDot` | 8px colored circle |
| `Table` | 10px uppercase headers, 6px cell padding, hover row |
| `Sidebar` | 200px↔52px collapse with Framer Motion, nav items |
| `TopBar` | 44px, breadcrumbs + search + notifications + avatar |
| `TabBar` | VS Code-style: multiple open, closable, horizontal scroll |
| `FilterBar` | Dropdowns for cluster/platform/date/classification |
| `Modal` | Framer Motion enter/exit, overlay |
| `Dropdown` | Floating, `shadow-float`, click outside to close |
| `SearchCommand` | Cmd+K palette (modal with search input + results) |
| `EmptyState` | Locus icon + title + description + CTA button |
| `Avatar` | 3 sizes, initials fallback |
| `ProgressBar` | 6px height, accent fill |
| `Toggle` | 36×20px track, 16px thumb |
| `Skeleton` | Shimmer animation, 3 variants |
| `Toast` | success/error/info, auto-dismiss |
| `ScoreGauge` | Semi-circular gauge, 0-100 |
| `Sparkline` | 60×16px inline SVG, trend coloring |
| `LocusLogo` | Inline SVG, `currentColor`, 3-stage animation, 3 variants |
| `WorkspaceSelector` | Dual dropdown (company + project) |

### ✅ Verify Before Proceeding

```bash
npm run dev
```

Create a temporary test page that renders every component. Visually check:
- Button is 30px tall with teal background
- Card has visible border on light bg
- MetricCard shows overline label
- Badge has colored pill
- Delete test page after verification.

---

## Step 6: Build App Shell

### Auth Layout (`src/app/(auth)/layout.tsx`)

Split-screen: left panel (form area) + right panel (brand visual). No sidebar.

### Dashboard Layout (`src/app/(dashboard)/layout.tsx`)

- `Sidebar` component (left)
- Main area with `TopBar` (top) + page content (below)
- Sidebar reads from Zustand store for collapsed state

### Zustand Stores (`src/stores/`)

```typescript
// src/stores/sidebar.ts
export const useSidebarStore = create<{
  collapsed: boolean;
  toggle: () => void;
}>((set) => ({
  collapsed: false,
  toggle: () => set((s) => ({ collapsed: !s.collapsed })),
}));

// src/stores/theme.ts — default: 'light'
export const useThemeStore = create<{
  mode: 'light' | 'dark';
  toggle: () => void;
}>((set) => ({
  mode: 'light',
  toggle: () => set((s) => ({ mode: s.mode === 'light' ? 'dark' : 'light' })),
}));

// src/stores/workspace.ts
// src/stores/notifications.ts
```

### ✅ Verify Before Proceeding

Navigate to `http://localhost:3000`. You should see:
- Sidebar on left with "deep  presence" compact logo at top
- Navigation items (Home, Analytics, etc.)
- Top bar with breadcrumbs
- Main content area showing placeholder
- Clicking sidebar toggle collapses to 52px icon rail

If sidebar doesn't render, check the dashboard layout imports. If styles are wrong, check globals.css.

---

## Step 7: Create Route Stubs

```
src/app/(auth)/login/page.tsx
src/app/(auth)/register/page.tsx
src/app/(auth)/join/page.tsx
src/app/onboarding/page.tsx
src/app/(dashboard)/page.tsx              → Home
src/app/(dashboard)/analytics/page.tsx
src/app/(dashboard)/analytics/lab/page.tsx
src/app/(dashboard)/content/page.tsx
src/app/(dashboard)/planner/page.tsx
src/app/(dashboard)/artifacts/page.tsx
src/app/(dashboard)/attribution/page.tsx
src/app/(dashboard)/settings/page.tsx
```

Each stub:
```tsx
import { EmptyState } from '@/components/ui';

export default function AnalyticsPage() {
  return <EmptyState title="Analytics" description="Agent 3 builds this page." />;
}
```

### ✅ Verify Before Proceeding

Click every sidebar nav item. Each route should render its placeholder EmptyState. No blank pages. No 404s.

---

## Step 8: Data Layer

Create `src/data/` with parsers reading REAL files from `data/artifacts/`:

| Parser File | Source | Output |
|-------------|--------|--------|
| `src/data/gap-report.ts` | `gap_analysis/lovable/gap_report.md` | `GapReport` |
| `src/data/site-audit.ts` | `site_audit/lovable/039d53f8.../report.md` | `SiteAudit` |
| `src/data/personas.ts` | `audience_personas/*/v1.md` | `Persona[]` |
| `src/data/knowledge-base.ts` | `knowledge_base/lovable/*/v1.md` | `KBDocument[]` |
| `src/data/voice-guide.ts` | `voice_style_guide/lovable/guide/v1.md` | `VoiceGuide` |
| `src/data/content-briefs.ts` | `content/carta/content/brief-*/` | `ContentBrief[]`, `ContentPiece[]` |
| `src/data/embeddings.ts` | `gap_analysis/lovable/visualizations/embedding_projections_*.json` | `EmbeddingPoint[]` |

All LFS files are available locally. Import JSON directly. Parse markdown with simple regex/string splitting (by `## ` headings for sections, by `- ` for bullet lists).

### ✅ Verify Before Proceeding

Create a temp test: import gap report data and log it. You should see 99 queries, SPA score 1.130, 25 gap briefs with real titles. If data is undefined or empty, the symlink or parser is broken.

---

## Step 9: Locus Logo Component

Build `src/components/ui/LocusLogo.tsx`:

```tsx
// Props: size (number), animated (boolean), variant ('full' | 'compact' | 'symbol')
// SVG: inline, uses currentColor
// Animation: 3 stages — dot fade-in (0.5s) → arc stroke draw (0.8s, staggered) → pulse (3s infinite)
// Full variant: 40px symbol + "deep  presence" wordmark (22px, weight 500)
// Compact variant: 16px symbol + "deep presence" (12px, weight 600)
// Symbol variant: just the SVG mark
```

The exact SVG paths are in `brand-system.md` Section 4 and `theme.config.ts` logo.svg.

### ✅ Verify Before Proceeding

Render `<LocusLogo variant="compact" animated />` in the sidebar. The Locus mark should draw itself on page load, then pulse. The wordmark should appear next to it.

---

## Troubleshooting

### shadcn CSS Variables Conflict
**Symptom:** Wrong colors everywhere — zinc grays instead of Slate.
**Fix:** After `shadcn init`, open `globals.css`. Delete ALL of shadcn's auto-generated `:root` and `.dark` CSS variable blocks. Replace with the brand tokens from theme.config.ts. shadcn adds `--background`, `--foreground`, `--card`, etc. — remove them all and use our `--bg`, `--surface`, `--text-primary` tokens instead.

### Tailwind Config Import Error
**Symptom:** `Cannot find module './src/lib/theme.config'`
**Fix:** Check the relative path. `tailwind.config.ts` is at project root, so the import path should be `'./src/lib/theme.config'`.

### Symlink Broken
**Symptom:** Data parsers return empty/undefined.
**Fix:** From `frontend/`, run `ls -la data/artifacts/`. If it shows broken link, recreate: `rm data/artifacts && ln -s ../../result-draft/artifacts data/artifacts`.

### Zustand Hydration Mismatch
**Symptom:** Server/client HTML mismatch warning for sidebar state.
**Fix:** Use `useEffect` to read store values on client only, or use Zustand's `persist` middleware with `skipHydration`.

### Google Fonts Not Loading
**Symptom:** Fallback sans-serif shows instead of Space Grotesk.
**Fix:** Check that the `<link>` tag is in `<head>` of `layout.tsx`, not inside `<body>`. Also check for CSP headers blocking external fonts.

---

## Completion Criteria

- [ ] `npm run dev` starts without errors
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] All 12 routes accessible via sidebar navigation
- [ ] Sidebar collapses/expands with animation
- [ ] Top bar shows breadcrumbs, search trigger, notification bell
- [ ] Light mode: Slate-tinted gray background (#F8F9FA), teal accent
- [ ] Dark mode: pure neutral gray (#171717), lighter teal accent
- [ ] All 25 components exist and export from `src/components/ui/index.ts`
- [ ] LocusLogo renders with draw animation
- [ ] Gap report data parser returns 99 queries with real titles
- [ ] Site audit parser returns score 98 with 8 dimensions
- [ ] At least one persona parsed from markdown files

## You Do NOT Touch After Completion

Everything. Other agents build on your foundation. Your job is done when theirs can begin.
