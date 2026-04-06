# Embedding Lab — Complete Handoff Context

> **Give this file to the next Claude Code agent to continue work on the Embedding Lab page.**
> Last updated: 2026-04-05

---

## What Was Built (v1 → v5)

The Embedding Lab at `/embedding-lab` went through 5 major iterations in this session. Here's the final state:

### Current Architecture: 4 Tabs

```
Tab 1: Territory Map     — D3 circle-packing with brand logos, full viewport height
Tab 2: Cluster Analysis  — Buyer journey cards + proximity analysis + scorecard table
Tab 3: Scatter Explorer  — 3,703-point SVG scatter with legend + side panel
Tab 4: Knowledge Graph   — D3 force-directed graph (clusters → queries → domains)
```

Plus a **55% wide cluster drawer** that opens when clicking any cluster (from territory map, scorecard, or analysis cards). The drawer has **5 internal tabs**: Overview | Domains | Queries | Structure | Embedding.

---

## Files (All in `src/app/(dashboard)/embedding-lab/`)

| File | Lines | Purpose |
|------|-------|---------|
| `page.tsx` | ~650 | Main page: 4 tabs, header with KPI badges, ScatterExplorerTab (inline), ClusterAnalysisTab (inline with buyer journey cards), KnowledgeGraphTab (wrapper) |
| `_components/territory-map.tsx` | ~300 | D3 SVG circle-packing. Sqrt-scale sizing, health-coded clusters (red dashed for danger zones), brand logos via Google Favicon API, hover tooltip card, click-to-zoom (2.5× D3 transition), zoom reset |
| `_components/territory-tab.tsx` | ~100 | Wraps territory map with engine filter toggle (All/ChatGPT/Claude/Perplexity/Gemini) + view mode toggle (Citations/Market Share/Authority). Full viewport height: `calc(100vh - 200px)` |
| `_components/cluster-drawer.tsx` | ~1200 | 55vw slide-in drawer with 5 tabs. Contains: OverviewSection, CompetitorTable (top 15 with structural signals), QueryIntelligence (16 expandable queries with content briefs), StructuralAnalysis (rates bars), EmbeddingScatter (mini D3 scatter). Uses Framer Motion for animation. |
| `_components/cluster-scorecard.tsx` | ~300 | Sortable 9-row table: Cluster, Citations, Your Share, Domains, Similarity (with mini bar), Coverage (progress bar), Rank, ChevronRight. Click row → opens drawer. |
| `_components/knowledge-graph.tsx` | ~600 | D3 force-directed graph. 9 cluster nodes (r=28) + 27 query nodes (top 3/cluster) + ~40 domain nodes (favicons). 3 edge types: cluster→query, query→domain, domain↔domain mind share. Hover highlights connections, click opens 280px side panel. Filter by cluster, toggle edge types. |
| `_components/brand-logo.tsx` | 29 | Google Favicon API with Clearbit fallback |
| `_components/data.ts` | ~280 | Types + data loading from processed JSON files |

## Data Pipeline

### Processing Script
`scripts/process-embedding-data.ts` — Run with `npx tsx scripts/process-embedding-data.ts`

Reads from `/Users/shashank/Documents/deep-embedding-lab-prototype/data/` (28.8MB raw pipeline data):
- `embedding_projections_umap.json` (805KB) — 3,703 points
- `embedding_projections_tsne.json` (811KB) — 3,703 points
- `gap_analysis_complete.json` (2.3MB) — 144 gaps with content briefs + exemplars + SPA stats
- `generation_spec.json` (11KB) — 9 cluster structural specs
- `enriched_citations.json` (25MB) — 1,804 citations with 44 structural signals each

Outputs to `public/data/`:
| File | Size | Content |
|------|------|---------|
| `embedding-umap.json` | 733KB | 3,703 UMAP points |
| `embedding-tsne.json` | 739KB | 3,703 t-SNE points |
| `gaps.json` | 213KB | 144 gaps + proximityStats + SPA + perClusterProximity |
| `cluster-profiles.json` | 39KB | 9 clusters with top 15 domains (each with structural signals), engine breakdown, proximity stats |
| `company-positioning.json` | 1KB | Company page distribution across clusters, centroid distances |
| `cluster-distances.json` | 1KB | 9×9 cosine distance matrix from 1536-dim centroids |

### Key Data Facts
- **4 engines** (not 5): openai, claude, perplexity, gemini — NO google_ai
- **Company domain**: www.insighthealth.ai (117 total citations, present in 7 of 9 clusters)
- **Danger zones** (0 company citations): Problem/Awareness, Best-of/Consideration
- **Top competitors**: innovaccer.com (54), healthcatalyst.com (46), arcadia.io (36), censinet.com (30)
- **SPA result**: t=8.34, p<0.001 — citation advantage is statistically significant
- **Similarity gap**: 0.061 (citation mean 0.635 vs company mean 0.574)
- **Company content skew**: 62.8% clusters near Boundary, 32.6% near Branded Evaluation

---

## Key Types (from data.ts)

```typescript
interface ClusterProfile {
  id: string; name: string; color: string;
  totalCitations: number; uniqueDomains: number; queryCount: number;
  companyCitations: number; companyShare: number; companyRank: number | null;
  presence: 'none' | 'minimal' | 'low' | 'moderate' | 'strong';
  avgWordCount: number; dominantContentType: string; dominantAuthorityType: string;
  structuralRates: Record<string, number>; faqRate: number; tableRate: number;
  requiredElements: string[]; exemplarThemes: string[];
  authoritySignals: Record<string, number>;
  proximity: { mean: number; std: number; count: number } | null;
  engineBreakdown: Record<string, number>;
  topDomains: DomainEntry[]; // top 15 with avgWordCount, avgHeaderCount, faqRate, tableRate, avgReadingLevel, contentType, authorityType
}

interface GapQuery {
  id: string; query: string; cluster: string; clusterId: string;
  gap: number; classification: string;
  companyCited: boolean; companyUrl: string | null; companySimilarity: number | null;
  avgCitationSimilarity: number;
  exemplars: GapExemplar[]; // top 2 with domain, url, similarity, structural signals
  companySignals: CompanySignals | null;
  contentBrief: ContentBrief; // wordCountRange, readingLevelRange, headerCountRange, etc.
}

interface EmbeddingPoint {
  id: string; x: number; y: number;
  type: 'query' | 'citation' | 'company';
  label: string; cluster: string; clusterId: string;
  queryId: string | null; similarity?: number;
}
```

---

## User Requirements (from deep interview)

### Core Vision
- **Territory intelligence platform** — users spend 2+ hours like SEMrush keyword research
- **Territory Map is the hero** — full page, bigger circles, zoom-into-cluster on click
- **Every metric drills down** — progressive disclosure, not content reduction
- **Executive board narrative** — ownership ("we own X"), progress ("closing the gap"), investment ("invest here")

### Territory Map
- Full viewport height, no scorecard taking space
- Circles bigger (maxR 25%), hover = rich tooltip card, click = D3 zoom to 2.5×
- Show: pages controlling AI, queries captured, blank spaces for monopolization
- 2D/3D view toggle (3D deferred to later — focus on making 2D amazing first)

### Cluster Drawer (55vw)
- 5 internal tabs: Overview | Domains | Queries | Structure | Embedding
- Top 15 competitors with FULL structural signals (word count, headers, FAQ, tables)
- Stacked drawers: clicking a domain should open ANOTHER drawer on top (domain-drawer.tsx not yet built)

### Cluster Analysis Tab
- Buyer journey cards: Awareness / Consideration / Decision stages
- Per-cluster proximity as individual cards (not flat bars)
- Scorecard table moved here from Territory Map

### Scatter Explorer
- Full viewport height
- Bottom legend with shape/color explanations + "How to read" instructions
- 280px side panel on point click with nearest neighbors

### Knowledge Graph
- D3 force-directed: clusters → queries → domains
- Mind share edges between domains cited for same queries
- Hover highlights connections, click opens side panel
- Filter by cluster, toggle edge types

---

## What's NOT Built Yet (Future Work)

1. **Domain Drawer** (`domain-drawer.tsx`) — Stacked second drawer when clicking a domain inside the cluster drawer. Should have 3 tabs: Overview (cross-cluster presence), Pages (cited URLs), Head-to-Head (vs your brand comparison). Infrastructure is wired (click handler exists in CompetitorTable), just needs the component.

2. **3D Territory Map** — User wants a 3D view toggle eventually. Deferred — focus on 2D first.

3. **Knowledge Graph 3D** — User mentioned wanting 3D for the knowledge graph (Three.js). Current implementation is 2D D3 force graph.

4. **Real-time data loading** — Currently all data is pre-processed static JSON. Future: API endpoints that regenerate on pipeline runs.

---

## Build Commands

```bash
# Process real data (run if raw data files change)
npx tsx scripts/process-embedding-data.ts

# Type check
npx tsc --noEmit

# Build
npm run build

# Dev server
npm run dev
# → http://localhost:3000/embedding-lab
```

## Tech Stack
- Next.js 14 App Router, TypeScript strict
- D3.js v7 for all visualizations (territory map, scatter, knowledge graph)
- Framer Motion for drawer animations
- Tailwind CSS with CSS custom properties from brand-system.md
- 4 AI engines: openai, claude, perplexity, gemini

## Brand System Rules
- CSS variables for all colors (`var(--accent)`, `var(--border)`, etc.)
- 1px borders on all cards/containers
- 10px uppercase tracking-[0.06em] section headers
- JetBrains Mono for data values (font-mono)
- Space Grotesk for text (font-display)
- Max font-weight: 600
- No shadows on cards (only shadow-float on floating elements)
- Real brand logos via Google Favicon API everywhere

## Memory Files (user preferences)
- `memory/feedback_embedding_lab_vision.md` — Territory intelligence page vision
- `memory/feedback_embedding_lab_v5.md` — Complete v5 requirements from interview
- `memory/feedback_drilldown_architecture.md` — Every metric must drill down
