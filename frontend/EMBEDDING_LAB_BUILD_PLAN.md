# Deep Embedding Lab — Agent Build Plan

> **Owner:** Shank (Product Lead)
> **Page:** Single complex page within the `(dashboard)` route group
> **Quality bar:** Production-grade. This is the most data-dense, visually ambitious page in Deep Presence.

---

## 1. Before You Write Any Code

Read these files first. They are the source of truth.

### Brand System
- **Find and read** the brand system / claiudfedesign tokens file in the frontend source (check `frontend/src/` for global CSS, Tailwind config, theme files, or a `brand-system` reference)
- This governs ALL styling decisions: colors, typography, spacing, borders, dark mode treatment
- Do NOT hardcode any color values or font families — import/reference from the brand system
- Follow the same component patterns, spacing conventions, and border treatments used across existing pages

### Existing Page Conventions
- **Scan:** `frontend/src/app/(dashboard)/` — understand how other pages are structured
- Look at `planner/`, `content/`, `settings/` for patterns: how they organize `_components/`, how they import data, how they handle page-level state
- Match these conventions exactly. The Embedding Lab should feel like it belongs in the same app.

### TypeScript Types
- **Read:** `frontend/src/types/` — especially any gap-analysis or embedding-related type files
- These types match the backend Pydantic schemas. Your mock data must conform to these types.
- If embedding types don't exist yet, create them in this directory following the same naming pattern.

### Backend Schemas (for mock data structure)
- The backend schemas live in `api/schemas/gap_data.py` and `api/schemas/content_data.py`
- Key models to understand and mirror: `EmbeddingPoint`, `EmbeddingProjectionResponse`, `QueryRow`, `ClusterSpecResponse`, `SignalAveragesResponse`, `SignalCorrelationRow`, `ClusterPatternRow`, `PlatformSummaryResponse`, `GapSummaryResponse`, `ClusterPerformanceRow`
- Your mock data must mirror these schemas field-for-field so Aryan can swap in real API calls without restructuring components

### Real Pipeline Output (for understanding what data looks like)
- The gap analysis pipeline (`core/gap_analysis/steps/s7_visualize.py`) generates embedding projections as JSON
- Each point has: `x, y, type (query/citation/company), id, label, cluster, cluster_id, query_id`
- The pipeline also generates Plotly HTML visualizations — we are NOT embedding those. We're building native D3 replacements.
- Understand what data exists so the mock data is realistic, not random noise

### Real Artifact Examples
- Check `artifacts/gap_analysis/` for real pipeline outputs (analysis.json, gap_report.json, enriched_citations.json, visualizations/)
- Look at the actual data structure, cluster names, query texts, domain names, gap scores to inform realistic mock data
- If the `data/artifacts/` symlink exists, use it to inspect real outputs

---

## 2. What This Page Does

The Embedding Lab visualizes where a brand stands in the AI citation landscape. It serves two ICPs from one page:

- **Non-tech (CMO/Growth):** Territory Control + Cluster Deep Dive — brand logos, competitive positioning, gap severity
- **Tech (SEO Engineer/Director):** Scatter Explorer + Correlation Analysis — raw embedding coordinates, structural signal correlations, platform divergence

These are 4 views on a single page, switched via tabs. Not separate routes.

---

## 3. The 4 Views

### View 1: Territory Control (Default)

The flagship visualization. A force-driven cluster map showing who owns which topic clusters across AI engines.

**What the user sees:**
- Share of Voice summary bar at the top (company citations / total citations across all clusters)
- Large circles representing query clusters, positioned by D3 force simulation
- Inside each cluster circle: brand logos sized by their citation dominance (citations × similarity composite)
- Cluster size proportional to query count
- Cluster border color encodes gap severity using the brand system's semantic colors
- Company's own logo gets distinct accent treatment (teal border, glow) — instantly findable
- Hover: other clusters fade, tooltip shows cluster name, gap badge, top brands + citation counts
- Click: navigates to Cluster Deep Dive (View 3) with that cluster loaded

**Technical guidance:**
- D3 `forceSimulation` with `forceCenter`, `forceManyBody`, `forceCollide` for cluster positioning
- Secondary force simulation per cluster for brand logo positioning within each circle
- Real logos from Clearbit: `https://logo.clearbit.com/{domain}` — fallback to `https://www.google.com/s2/favicons?domain={domain}&sz=64`, then text
- SVG rendering (not canvas — element count is manageable at ~50-80)
- Consider Nadieh Bremer's organic circle technique (jittered points + d3.curveBasisClosed for imperfect circle borders). Research visualcinnamon.com if unfamiliar.

**Data to mock (derive structure from backend schemas):**
- Cluster list with: name, id, query count, avg gap, gap classification
- Per-cluster brand breakdown: domain, citation count, avg similarity, platforms, isCompany flag
- Aggregates: total citations, company citations, cluster count, query count

### View 2: Scatter Explorer

Raw 2D embedding space for technical users.

**What the user sees:**
- UMAP / t-SNE toggle
- Point type filters: Queries (circles), Citations (squares), Company (triangles)
- 500-800 points colored by cluster, company points in teal
- Hover tooltip with point metadata
- Click opens slide-in detail panel
- Proximity lines from hovered query to top-3 nearest citations
- Cluster color legend

**Technical guidance:**
- Canvas rendering for performance (500+ points at 60fps during pan/zoom)
- d3.zoom() for pan/zoom behavior
- Hit detection via nearest-point search on mousemove
- requestAnimationFrame render loop, batch draws by point type
- Data matches `EmbeddingProjectionResponse` schema exactly

### View 3: Cluster Deep Dive

Forensic view of a single cluster. Entered by clicking from View 1 or via dropdown.

**What the user sees:**
- Cluster header: name, gap severity badge, query count, company's rank
- Citation Share: horizontal bar chart with brand logos + bars
- Structural Fingerprint: radar chart overlaying top-cited vs. company structural profiles. Axes: faq_rate, definition_opening, key_takeaways, comparison_table, step_by_step, research_refs
- Query Table: all queries in this cluster sorted by gap severity. Columns: query text, gap score (color-coded), company sim, citation sim, top domain (with logo). Expandable rows.

**Data to mock:**
- Brand citation breakdown per cluster
- Structural fingerprints (from `cluster_fingerprints` in SignalAveragesResponse + company signals)
- Query list per cluster (from QueryRow schema)

### View 4: Correlation Analysis

What structural signals drive AI citation.

**What the user sees:**
- Cluster filter pills (All + per-cluster)
- Diverging bar chart: ~40 signals ranked by correlation with citation similarity. Positive (green) right, negative (red) left. Category dots per signal.
- Platform Signal Divergence: 4-column grid showing top signals per platform (ChatGPT, Claude, Gemini, Perplexity)

**Data to mock:**
- Signal correlations (~40 entries from SignalCorrelationRow schema)
- Per-platform signal rankings

---

## 4. Mock Data Approach

Create a mock data file following whatever convention exists in the project (check existing data files).

**Requirements:**
- Structure MUST match backend Pydantic schemas field-for-field
- Use realistic domains: hubspot.com, stripe.com, cloudflare.com, crowdstrike.com, semrush.com, ahrefs.com, vercel.com
- Company domain: "deeppresence.io"
- 6-10 clusters with realistic names (e.g., SaaS Pricing Strategy, Enterprise Security, API Documentation, AI Content Marketing)
- Query texts should sound like real questions people ask AI engines
- Gap scores: realistic distribution (mostly 0.2-0.5, some outliers)
- Scatter: 500-800 points with per-cluster spatial grouping
- Export UMAP and t-SNE as separate datasets (same points, different coordinates)
- If you can read real artifacts for reference (gap_report.json, analysis.json), use those as a guide for realistic values

---

## 5. File Structure

Follow the existing convention in `frontend/src/app/(dashboard)/`. Place the page using the same pattern as planner, content, settings:

```
frontend/src/app/(dashboard)/embedding-lab/
├── page.tsx
└── _components/
    ├── territory-control.tsx
    ├── scatter-explorer.tsx
    ├── cluster-deep-dive.tsx
    ├── correlation-analysis.tsx
    └── (shared components as needed — brand-logo, gap-badge, etc.)
```

Mock data and types go wherever the existing convention puts them.

---

## 6. Key Technical Decisions

- **D3.js** for Territory Control (force simulation) and Scatter Explorer (canvas + zoom). Install if not present.
- **Recharts or D3** for the radar chart — use whichever is already in the project's dependencies.
- **Canvas** for the scatter plot. SVG for everything else.
- **No Plotly iframes.** The backend generates HTML viz files — we don't use those.
- **No routing.** Single page, tab state. Clicking a cluster sets state, doesn't navigate.
- **All data from mock files.** No fetch calls. But structure the data access layer so swapping in real API calls is a clean replacement.

---

## 7. Visual Inspiration: Nadieh Bremer / Visual Cinnamon

This page draws from Nadieh Bremer's D3 techniques (visualcinnamon.com):

- **Circle packing + force hybrid:** Her Google cats/dogs project combined d3.packSiblings with d3.forceSimulation. We use this pattern for brand logos inside cluster circles.
- **Organic circle borders:** Jitter points around circle edge, connect with d3.curveBasisClosed for hand-drawn feel on cluster boundaries.
- **Progressive disclosure via zoom:** Territory (all clusters) → Cluster Deep Dive (one cluster) → Query detail.
- **Canvas for density, SVG for interactivity.**

Apply her techniques within the Deep Presence brand system — dark mode, sharp aesthetic, teal accents. Not her light/pastel style.

---

## 8. Polish & Interactions

- Stagger cluster circles on load (80ms delay, scale 0.8→1.0, 300ms ease-out)
- Share of Voice bar animates 0→actual width
- Tab crossfade (150ms)
- Hover: 150ms transitions, cursor pointer, logo scale(1.05)
- Canvas scatter: requestAnimationFrame, batch draws by type

---

## 9. What NOT to Build

- No auth logic — assume authenticated
- No real API calls — mock data only
- No Content Studio integration — read-only analytics page
- No temporal comparison (future feature)
- No "What If" simulator (future feature)
- No Plotly iframes
- No mobile (1280px+ only)
- No separate routes — tabs on one page

---

## 10. Definition of Done

- All 4 views render with mock data
- Territory Control: D3 force positions clusters without overlap, Clearbit logos load with fallbacks
- Scatter Explorer: 600+ points at 60fps, pan/zoom, tooltips
- Cluster Deep Dive: radar overlay, sortable query table, brand logos
- Correlation Analysis: diverging bars, cluster filter works
- Brand system applied from the project's brand system file — not hardcoded values
- Mock data matches backend schemas exactly
- No TypeScript errors
- Page is cohesive with the rest of the dashboard