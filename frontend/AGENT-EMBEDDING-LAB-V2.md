# Agent — Embedding Lab v2 (Production Rebuild)

> **Read CLAUDE.md and brand-system.md first, then this file.** This is a FULL REBUILD of `/embedding-lab`.
> **Reference the Cursor prototype** at `/Users/shashank/Documents/deep-embedding-lab-prototype/` for territory map inspiration — study its data/, js/, and css/ folders. The prototype is in a SEPARATE codebase (vanilla HTML/JS/D3), not in this Next.js project. Use it as visual reference only — rebuild everything natively in React/TypeScript/D3.

---

## Mission

Build the Embedding Lab — the advanced analytics page that shows WHERE your brand has territory in the AI citation landscape, WHERE the gaps are, and HOW different AI engines see your space differently.

This page serves TWO audiences:
- **CMO / Growth Marketer**: Territory Map (Tab 1) and Gap Intelligence (Tab 2) — visual, actionable, no jargon
- **Technical SEO / Engineer**: Engine Intelligence (Tab 3) and Embedding Space (Tab 4) — raw data, scatter plots, structural analysis

**DELETE** everything at `/embedding-lab` and rebuild from scratch.

---

## Files You Own

```
src/app/(dashboard)/embedding-lab/page.tsx
src/app/(dashboard)/embedding-lab/_components/
```

**Install D3 if not present:** `npm install d3 @types/d3`

---

## MANDATORY LAYOUT STANDARDS

Same density as all other pages:

```
Page horizontal padding: max 24px
Section gaps: 16px
Card internal padding: 12px-14px
Table headers: 11px uppercase, letter-spacing 0.05em
Table body: 13px
Data values: JetBrains Mono
Text: Space Grotesk
1px borders on all cards
CSS variables for all colors
Real brand logos via Google Favicon API everywhere
```

---

## PAGE HEADER

```
Embedding Lab
Competitive territory intelligence powered by semantic analysis
```

Title: 22px font-weight 600. Subtitle: 13px var(--text-secondary).

### Top Bar Stats (right-aligned, same row as title)

```
9 TERRITORIES · 2 DANGER ZONES · 23 CRITICAL GAPS · 767 COMPETITORS
```

Four stat badges: count in JetBrains Mono 13px font-weight 600, label in 10px uppercase var(--text-secondary). "DANGER ZONES" in red, "CRITICAL GAPS" in amber, others in default color.

### Tab Navigation (below header, full-width)

```
[Territory Map]  [Gap Intelligence]  [Engine Intelligence]  [Embedding Space]
```

Four tabs. Active: accent bottom border (2px), accent text, font-weight 600. Inactive: var(--text-secondary). 13px text. Each tab icon: small SVG before text (grid icon for Territory, bar chart for Gap, globe for Engine, scatter for Embedding).

---

## TAB 1: TERRITORY MAP (Default — for CMOs)

This is the signature visualization. A D3 circle-packed force layout showing competitive territories.

### Layout: Map (65%) + Intelligence Panel (35%)

`display: grid; grid-template-columns: 1fr 420px; gap: 0;`

The intelligence panel is a right sidebar that slides in when a cluster is clicked. Default state: panel shows aggregate stats.

### Territory Map Visualization (Left, 65%)

**Use D3.js for this visualization.** Render to SVG (not Canvas — we need interactivity on each element).

#### Circle Packing Structure

Each **cluster** is a large circle. Inside each cluster circle are smaller circles representing **competitor brands**, sized by their citation share within that cluster.

```
Cluster circle size = total citations in cluster
Brand circle size = brand's citation count in that cluster
Brand circle position = D3 force simulation within parent cluster
```

#### Visual Design

**Cluster circles:**
- Stroke: 1px var(--border)
- Fill: transparent (just the outline containing brand logos)
- Label: cluster name + citation count + share percentage, positioned at top of circle
- "No presence" label in red if the user's brand has zero citations in this cluster
- "Your presence: X% share (#N)" in accent/green if present

**Brand circles (inside clusters):**
- Size: proportional to citation count (min 16px, max 60px diameter)
- Content: Real brand favicon centered in the circle
- Favicon fetched via Google Favicon API: `https://www.google.com/s2/favicons?domain={domain}&sz=64`
- Circle fill: white (light mode) or var(--surface) (dark mode), with 1px border
- YOUR brand: teal ring (2px solid var(--accent)), slightly pulsing glow animation
- On hover: tooltip with domain, citations, share %

**Mind share competitor differentiation:**
- Direct competitors (same product category): filled circles with solid border
- Mind share competitors (different product, same queries): circles with DASHED border
- Authority sources (gov, edu, org): circles with DOTTED border, slightly transparent
- Add a small legend below the map showing the three types

**View toggle** (top-right of map area): "Size by Citations" / "Size by Market Share" / "Color by Authority Type"

When "Color by Authority Type" is selected:
- Commercial: default color
- Government (.gov): blue tint
- Educational (.edu): green tint  
- Organization (.org): purple tint
- News/Media: amber tint

#### D3 Implementation

```typescript
// Force simulation per cluster
const simulation = d3.forceSimulation(clusterNodes)
  .force("center", d3.forceCenter(cx, cy))
  .force("collision", d3.forceCollide().radius(d => d.radius + 2))
  .force("charge", d3.forceManyBody().strength(-5))
  .alphaDecay(0.02);

// Cluster layout using d3.packSiblings for initial positions
const packed = d3.packSiblings(clusters.map(c => ({ ...c, r: c.radius })));
const enclosure = d3.packEnclose(packed);
```

**Cluster click:** Zoom into the cluster (D3 zoom transition, 400ms). Show only that cluster's brands at larger scale. Intelligence panel updates with cluster-specific data.

**Double-click or "Reset View" button:** Zoom back to overview.

### Intelligence Panel (Right, 35% — 420px)

Slides in with content when a cluster is selected. Default shows aggregate view.

#### Default State (no cluster selected)

```
TERRITORY OVERVIEW

9 clusters analyzed
767 unique competitors tracked
229 total citations mapped

YOUR COVERAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━  4 of 9 clusters
You have presence in 4 clusters. 5 clusters have zero coverage.

DANGER ZONES (0 citations)
• Problem/Awareness — 229 citations, 159 domains
• Best-of/Consideration — 201 citations, 142 domains

TOP OPPORTUNITIES
1. Problem/Awareness — 26.7% gap, 16 queries uncovered
2. Best-of/Consideration — 22.4% gap, 12 queries uncovered
```

#### Cluster Selected State

When a cluster circle is clicked, panel shows:

```
● Problem/Awareness
229 citations · 159 unique domains · fragmented
Your presence: No presence [RED]

DOMAIN LEADERBOARD
1  [favicon] www.cms.gov         10   4.4%
2  [favicon] healthcatalyst.com   9   3.9%
3  [favicon] www.cdc.gov          8   3.5%
4  [favicon] innovaccer.com       5   2.2%
5  [favicon] psnet.ahrq.gov       4   1.7%
6  [favicon] www.aafp.org         4   1.7%
7  [favicon] www.ncqa.org         4   1.7%
8  [favicon] link.springer.com    4   1.7%

COMPETITOR TYPES
Direct: 3 brands (14%)
Mind share: 8 brands (36%)
Authority: 11 sources (50%)  ← gov, edu, org

AI ENGINE BREAKDOWN
Gemini     ████████████████████  56
OpenAI     ████████████████      43
Claude     ████████████████████  65
Perplexity ██████████████████    65

TOP CONTENT GAPS (16 TOTAL, 2 CRITICAL)
"How to improve HCC risk adjustment..."    26.7%  Not cited
"How to operationalize SDoH data..."       25.9%  Not cited
"How to improve Medicare Star Ratings..."   12.6%  Not cited
[Create content for this cluster →]

WINNING CONTENT PROFILE
1400 AVG WORDS     Blog_or_article CONTENT TYPE
Commercial_or_media AUTHORITY    16 QUERIES
[Headers] [Lists] [Statistics] [FAQ] [Tables]  ← structural features
```

Each section has 11px uppercase headers. Domain leaderboard rows: rank (JetBrains Mono 11px) + favicon (14px) + domain (12px) + count (JetBrains Mono 12px) + share % (JetBrains Mono 11px).

Engine breakdown: colored horizontal bars per engine, with count right-aligned.

Content gaps: query text (12px), gap percentage (JetBrains Mono 12px, red), "Not cited" badge. "Create content" button links to Content Planner.

Winning Content Profile: 4 metric cards (2×2 grid) showing avg words, content type, authority type, query count. Below: structural feature tags as pills.

### Engine-Specific Territory Toggle

Below the main map, add toggle buttons:

```
View: [All Engines]  [ChatGPT]  [Claude]  [Perplexity]  [Google AI]  [Gemini]
```

When an engine is selected, the territory map RECALCULATES — brand circle sizes change to reflect that engine's citations only. This shows which engines have different competitive landscapes for the same clusters.

---

## TAB 2: GAP INTELLIGENCE (for Growth Marketers)

This tab translates embedding gaps into actionable content strategy. Table-first design.

### KPI Strip (3 cards)

```
TOTAL GAPS          CRITICAL GAPS        AVG GAP SCORE
47                  23                   0.18
across 9 clusters   gap > 0.15           lower = closer to cited content
```

### Gap Priority Table (full width — primary content)

Sorted by Opportunity Score (composite of gap size × query volume × 1/competitive density).

| Column | Width | Content |
|--------|-------|---------|
| Query | 25% | Query text (13px font-weight 500) + cluster badge below (11px) |
| Gap | 7% | Gap score, JetBrains Mono, colored: red >0.15, amber 0.05-0.15, green <0.05 |
| Classification | 10% | Badge: "Significant gap" (red), "Gap to close" (amber), "Roughly equal" (green), "Company wins" (teal) |
| Your Content | 15% | URL of your best matching content, or "No content" in red. Truncated with favicon |
| Top Cited | 15% | Domain + URL of top cited content with favicon. Mind share competitors marked with dashed icon |
| Engines | 10% | Engine favicons (filled if cited there, empty if not). Shows which engines cite competitors for this query |
| Opportunity | 8% | Score (JetBrains Mono), green = high opportunity |
| Action | 10% | [Create content →] or [Improve →] button. "Create" if no content, "Improve" if content exists but gap is large |

Row click → expands inline to show: your content's structural signals vs top cited content's structural signals side by side, plus "What you need to add" checklist.

**Filter bar above table:** Cluster dropdown, Classification dropdown (All / Significant / Gap to close / Equal / Company wins), Engine dropdown.

### Content Coverage Radar

Below the table: a compact visualization showing coverage per cluster.

```
CLUSTER COVERAGE — How many queries you cover vs total in each cluster

Mechanism          ████████████░░░░  12/16 queries (75%)
Boundary           ████████░░░░░░░░   8/16 queries (50%)
Branded Evaluation █████████████░░░  13/17 queries (76%)
Category Comparison ██████░░░░░░░░░   6/14 queries (43%)
Decision Criteria   ████░░░░░░░░░░░░  4/15 queries (27%)
Definition          ███░░░░░░░░░░░░░  3/12 queries (25%)
Feature Verification ██████████░░░░░  10/15 queries (67%)
Problem/Awareness   ░░░░░░░░░░░░░░░░  0/16 queries (0%)   ← RED
Best-of/Consider.   ░░░░░░░░░░░░░░░░  0/14 queries (0%)   ← RED
```

Each bar: filled portion in accent, empty in var(--border). Fraction and percentage right-aligned in JetBrains Mono. 0% clusters highlighted in red.

### White Space Map

Section below coverage radar. Shows clusters where you have ZERO content but competitors are being cited.

```
WHITE SPACES — Territories with zero presence

● Problem/Awareness
  229 citations from 159 competitors · Dominated by gov/edu sources (cms.gov, cdc.gov)
  Top query: "How to improve HCC risk adjustment accuracy" — 26.7% gap
  Content strategy: Practitioner-focused guides (not competing with reference sources)
  [Enter this territory → Content Planner]

● Best-of/Consideration
  201 citations from 142 competitors · Mixed commercial and authority sources
  Top query: "Best healthcare analytics platforms comparison" — 22.4% gap
  Content strategy: Comparison and evaluation content
  [Enter this territory → Content Planner]
```

Each white space: red dot, cluster name (14px font-weight 600), stats (12px), top query with gap, recommended strategy, action button.

---

## TAB 3: ENGINE INTELLIGENCE (for Everyone)

Shows how different AI engines see the same topics differently.

### Engine Comparison Grid (top section)

5 columns, one per engine. Each column is a card:

```
┌─────────────────┐
│ [fav] ChatGPT   │
│                  │
│ 312 citations    │  ← 24px JetBrains Mono
│                  │
│ Top domain:      │
│ [fav] cms.gov    │
│                  │
│ Unique citations │
│ 45 (not on other │
│ engines)         │
│                  │
│ Preferred:       │
│ Blog articles    │
│ FAQ sections     │
│ 1400+ words      │
└─────────────────┘
```

Each card: 1px border, 14px padding. Citation count in 24px mono. Top domain with favicon. Unique citation count (citations ONLY on this engine, not shared). Preferred content traits (derived from structural signals).

### Engine Divergence Table

Full-width table showing queries where engines DISAGREE on who to cite.

| Query | ChatGPT | Claude | Perplexity | Google AI | Gemini | Agreement |
|-------|---------|--------|------------|-----------|--------|-----------|
| "HCC risk adjustment" | cms.gov | healthcatalyst | cms.gov | — | innovaccer | 40% |
| "care gap detection" | innovaccer | — | accountablehq | cms.gov | — | 0% |

Each cell shows the favicon + domain of who that engine cites. "—" if engine doesn't cite anyone. Agreement column: percentage of engines that agree on the same domain. Low agreement (red) = opportunity to target specific engines.

Sort by Agreement ascending (most divergent first).

### Per-Engine Territory Map (reuses Tab 1 component)

Instead of showing all engines combined, show the territory map filtered to ONE engine at a time.

Toggle: [All Engines] [ChatGPT] [Claude] [Perplexity] [Google AI] [Gemini]

When switched, the territory map recalculates with that engine's citation data only. Brand circles resize. Some brands may disappear (not cited on this engine).

This shows: "On ChatGPT, cms.gov dominates Problem/Awareness. On Claude, healthcatalyst leads. On Perplexity, accountablehq wins." — engine-specific competitive intelligence.

Use the SAME D3 territory map component from Tab 1, just pass different data.

---

## TAB 4: EMBEDDING SPACE (Technical Users)

Raw embedding visualizations rebuilt natively in D3 within our design system.

### Sub-tab Navigation

```
[Scatter Explorer]  [Proximity Analysis]  [Content DNA]  [Authority & Similarity]
```

### Scatter Explorer (default sub-tab)

D3 scatter plot with UMAP/t-SNE toggle.

**Toggle:** [UMAP] [t-SNE] — switches between projection methods.
**Color by:** [Cluster] [Type] [Gap Score] — dropdown.

**Point types:**
- Queries: circles (6px radius), colored by cluster
- Citations: squares (5px), colored by cluster  
- Company content: triangles (7px), red/orange, YOUR content highlighted with accent ring

**Interactions:**
- Pan and zoom (D3 zoom behavior)
- Hover: tooltip with label, type, cluster, similarity/gap score
- Click: selects point, shows detail in right panel (320px)
- Brush/lasso: select multiple points for aggregate stats

**Right panel on point selection:**

```
www.trustradius.com                    CITATION
trustradius.com/compare/cerner-health...
[Branded Evaluation]

SOURCE INTELLIGENCE
AI Engine:      Gemini
Authority:      Commercial Or Media
Content type:   —

STRUCTURAL SIGNALS
976 WORDS    0 HEADERS    0 LIST ITEMS

CONTENT FEATURES
[Definition]
```

### Proximity Analysis (sub-tab)

Select any of your company's content points → see its nearest neighbors:

```
YOUR CONTENT: insighthealth.ai/blog/hcc-risk-adjustment
Cluster: Mechanism · Similarity to centroid: 0.72

NEAREST CITATIONS (what AI engines cite for similar queries)
1. healthcatalyst.com/resources/...    similarity: 0.85    ChatGPT, Claude
2. cms.gov/innovation/...              similarity: 0.82    All engines
3. innovaccer.com/blog/...             similarity: 0.78    Perplexity

GAP TO CITATION SWEET SPOT: 0.13
Your content is 0.13 away from the citation centroid.
To close this gap: add FAQ sections, increase to 2000+ words, add comparison tables.

NEAREST COMPANY CONTENT (potential cannibalization)
1. insighthealth.ai/blog/risk-models   similarity: 0.91   ⚠ High overlap
   Consider differentiating or merging these pages.
```

### Content DNA (sub-tab)

Compare structural signals between two selected points side by side.

Select point A + point B → see comparison:

```
                        Your content    Top cited (cms.gov)
Word count              976             2,400
Headers                 0               14
FAQ sections            No              Yes
Comparison tables       No              Yes
Lists                   0               8
External citations      2               12
Reading level           12.5            9.2
Schema markup           No              Yes
```

Visual: horizontal bars for each signal, two bars per row (yours vs cited), showing the gap.

### Authority & Similarity (sub-tab)

Radial plot showing your content's position relative to the citation centroid for each cluster.

Center = citation centroid (what AI engines cite most). Your content points plotted at their actual distance from centroid. Closer = more likely to be cited.

```
Cluster              Distance    Status
Mechanism            0.08        ✓ Well positioned
Boundary             0.12        ⚠ Room to improve
Branded Evaluation   0.05        ✓ Excellent
Category Comparison  0.22        ✗ Far from sweet spot
Decision Criteria    0.35        ✗ Needs major work
```

---

## MOCK DATA

### Clusters (9 clusters, matching the Cursor prototype)

```typescript
const CLUSTERS = [
  { id: "cl1", name: "Mechanism", citations: 173, share: 11.6, domains: 103, presence: "moderate", yourShare: 1.6, yourRank: 1 },
  { id: "cl2", name: "Boundary", citations: 184, share: 1.6, domains: 103, presence: "moderate", yourShare: 1.6, yourRank: 1 },
  { id: "cl3", name: "Category Comparison", citations: 156, share: 5.0, domains: 89, presence: "low", yourShare: 0.8, yourRank: 4 },
  { id: "cl4", name: "Decision Criteria", citations: 200, share: 0.5, domains: 112, presence: "minimal", yourShare: 0.2, yourRank: 8 },
  { id: "cl5", name: "Definition", citations: 131, share: 1.0, domains: 78, presence: "low", yourShare: 0.5, yourRank: 6 },
  { id: "cl6", name: "Problem/Awareness", citations: 229, share: 0, domains: 159, presence: "none", yourShare: 0, yourRank: null },
  { id: "cl7", name: "Best-of/Consideration", citations: 201, share: 0, domains: 142, presence: "none", yourShare: 0, yourRank: null },
  { id: "cl8", name: "Branded Evaluation", citations: 176, share: 4.5, domains: 95, presence: "moderate", yourShare: 2.1, yourRank: 2 },
  { id: "cl9", name: "Feature Verification", citations: 170, share: 1.0, domains: 98, presence: "low", yourShare: 0.6, yourRank: 5 },
];
```

### Top Competitors Per Cluster (sample for Problem/Awareness)

```typescript
const PROBLEM_AWARENESS_COMPETITORS = [
  { domain: "www.cms.gov", citations: 10, share: 4.4, type: "authority" },
  { domain: "www.healthcatalyst.com", citations: 9, share: 3.9, type: "direct" },
  { domain: "www.cdc.gov", citations: 8, share: 3.5, type: "authority" },
  { domain: "innovaccer.com", citations: 5, share: 2.2, type: "direct" },
  { domain: "psnet.ahrq.gov", citations: 4, share: 1.7, type: "authority" },
  { domain: "www.aafp.org", citations: 4, share: 1.7, type: "mindshare" },
  { domain: "www.ncqa.org", citations: 4, share: 1.7, type: "authority" },
  { domain: "link.springer.com", citations: 4, share: 1.7, type: "mindshare" },
];
```

### Gap Data (sample, 10 queries across clusters)

```typescript
const GAP_QUERIES = [
  { query: "How can we improve HCC risk adjustment accuracy and reduce coding misses?", cluster: "Problem/Awareness", gap: 0.267, classification: "significant_gap", yourContent: null, topCited: { domain: "healthcatalyst.com", url: "healthcatalyst.com/resources/hcc" }, engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: false }, opportunityScore: 0.92 },
  { query: "How can we operationalize SDoH data to target interventions?", cluster: "Problem/Awareness", gap: 0.259, classification: "significant_gap", yourContent: null, topCited: { domain: "innovaccer.com", url: "innovaccer.com/blog/sdoh" }, engines: { chatgpt: true, claude: false, perplexity: true, gemini: true, google_ai: true }, opportunityScore: 0.88 },
  { query: "What are common failure modes of healthcare predictive models?", cluster: "Mechanism", gap: 0.147, classification: "gap_to_close", yourContent: { url: "insighthealth.ai/blog/predictive-models" }, topCited: { domain: "nature.com", url: "nature.com/articles/ml-healthcare" }, engines: { chatgpt: true, claude: true, perplexity: false, gemini: true, google_ai: true }, opportunityScore: 0.71 },
  { query: "What are the limitations of using claims data alone for care gap detection?", cluster: "Mechanism", gap: 0.130, classification: "gap_to_close", yourContent: { url: "insighthealth.ai/blog/claims-data" }, topCited: { domain: "accountablehq.com", url: "accountablehq.com/post/claims-data" }, engines: { chatgpt: false, claude: true, perplexity: true, gemini: false, google_ai: true }, opportunityScore: 0.65 },
  { query: "Best healthcare analytics platforms comparison 2026", cluster: "Best-of/Consideration", gap: 0.224, classification: "significant_gap", yourContent: null, topCited: { domain: "g2.com", url: "g2.com/categories/healthcare-analytics" }, engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: true }, opportunityScore: 0.95 },
  { query: "How do we evaluate bias and fairness risk in AI models?", cluster: "Mechanism", gap: 0.103, classification: "gap_to_close", yourContent: { url: "insighthealth.ai/blog/ai-fairness" }, topCited: { domain: "arxiv.org", url: "arxiv.org/abs/2103.12345" }, engines: { chatgpt: true, claude: true, perplexity: false, gemini: false, google_ai: true }, opportunityScore: 0.58 },
  { query: "HIPAA compliance requirements for AI in healthcare", cluster: "Boundary", gap: 0.085, classification: "gap_to_close", yourContent: { url: "insighthealth.ai/blog/hipaa-ai" }, topCited: { domain: "www.hhs.gov", url: "hhs.gov/hipaa/ai-guidance" }, engines: { chatgpt: true, claude: true, perplexity: true, gemini: true, google_ai: true }, opportunityScore: 0.45 },
  { query: "Insight Health vs Epic analytics capabilities", cluster: "Branded Evaluation", gap: 0.042, classification: "roughly_equal", yourContent: { url: "insighthealth.ai/blog/vs-epic" }, topCited: { domain: "insighthealth.ai", url: "insighthealth.ai/blog/vs-epic" }, engines: { chatgpt: true, claude: true, perplexity: true, gemini: false, google_ai: false }, opportunityScore: 0.22 },
  { query: "Medicare Advantage Star Ratings improvement strategies", cluster: "Problem/Awareness", gap: 0.126, classification: "gap_to_close", yourContent: null, topCited: { domain: "cms.gov", url: "cms.gov/Medicare/star-ratings" }, engines: { chatgpt: true, claude: false, perplexity: true, gemini: true, google_ai: true }, opportunityScore: 0.78 },
  { query: "How to reduce 30-day hospital readmissions with data analytics?", cluster: "Problem/Awareness", gap: 0.104, classification: "gap_to_close", yourContent: null, topCited: { domain: "healthcatalyst.com", url: "healthcatalyst.com/readmissions" }, engines: { chatgpt: true, claude: true, perplexity: true, gemini: false, google_ai: true }, opportunityScore: 0.74 },
];
```

### Embedding Projection Data (for Scatter Explorer)

Generate 200+ points for the scatter explorer. Each point:

```typescript
interface EmbeddingPoint {
  id: string;
  x: number;           // UMAP coordinate
  y: number;
  tsne_x: number;      // t-SNE coordinate
  tsne_y: number;
  type: "query" | "citation" | "company";
  label: string;       // query text, URL, or page title
  cluster: string;
  clusterId: string;
  similarity?: number;
  gapScore?: number;
  domain?: string;     // for citations
  engine?: string;     // which AI engine cited this
  authorityType?: "commercial" | "government" | "educational" | "organization" | "news";
  wordCount?: number;
  headers?: number;
  hasFaq?: boolean;
}
```

Generate realistic clusters of points:
- Queries: 50 points, clustered by topic, blue circles
- Citations: 100 points, near their matching queries, green squares
- Company content: 30 points, red triangles, some close to citations (well-positioned), some far (gaps)

Use a seed-based random number generator so the scatter plot is deterministic between renders.

---

## D3 TERRITORY MAP COMPONENT

### Key Technical Decisions

- **SVG rendering** (not Canvas) — we need per-element interactivity (hover, click)
- **D3 force simulation** for brand placement within clusters
- **D3 packSiblings** for cluster-level layout
- **D3 zoom** for click-to-zoom into clusters
- **Real favicons** as images inside SVG circles
- **Responsive** via viewBox

### Component Structure

```typescript
// TerritoryMap.tsx
interface TerritoryMapProps {
  clusters: ClusterData[];
  engineFilter: string; // "all" | "chatgpt" | "claude" | etc.
  viewMode: "citations" | "market_share" | "authority";
  onClusterSelect: (clusterId: string | null) => void;
  selectedCluster: string | null;
}
```

### Performance

- Limit brand logos to top 8 per cluster (others become generic dots)
- Debounce force simulation ticks
- Use `will-change: transform` on zoomed elements
- Lazy-load favicons with IntersectionObserver

---

## ANIMATIONS

```css
@keyframes fadeUp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
@keyframes slideInRight { from { transform:translateX(100%); } to { transform:translateX(0); } }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }
```

- Intelligence panel: slideInRight 200ms when cluster selected
- Cluster zoom: D3 zoom transition 400ms
- Table rows: fadeUp with 25ms stagger
- Your brand circle: pulse animation (subtle, 3s cycle)
- Tab switch: fade content 150ms
- Hover transitions: 150ms on all elements

---

## VERIFICATION

```bash
npm install d3 @types/d3
npm run dev
npx tsc --noEmit
```

1. Page loads at `/embedding-lab` with Territory Map as default tab
2. Territory map: 9 cluster circles rendered with D3 force simulation
3. Each cluster has brand logos (real favicons) inside
4. YOUR brand has teal ring and pulse animation
5. Mind share competitors: dashed border. Authority sources: dotted border
6. Click cluster: zooms in, intelligence panel updates
7. Intelligence panel: domain leaderboard, engine breakdown, content gaps, winning profile
8. Engine toggle: territory map recalculates when switching engines
9. "Create content →" buttons in intelligence panel work (link to Content Planner)
10. Gap Intelligence tab: gap priority table with 10+ rows, all columns
11. Gap table: expandable rows showing structural comparison
12. Coverage radar: bars for all 9 clusters with coverage fractions
13. White spaces: 2 entries with action buttons
14. Engine Intelligence tab: 5 engine cards with unique citation counts
15. Divergence table: queries sorted by lowest agreement
16. Per-engine territory map toggle works
17. Embedding Space tab: D3 scatter with 200+ points
18. UMAP/t-SNE toggle works
19. Color by Cluster/Type/Gap Score works
20. Point click: detail panel shows structural signals
21. Proximity Analysis: nearest neighbors list
22. Content DNA: side-by-side comparison
23. All favicons loading (Google Favicon API)
24. All font sizes match brand system
25. `npm run build` succeeds

---

## COMPLETION CRITERIA

- [ ] Territory Map renders with D3 (9 clusters, brand logos, force simulation)
- [ ] Competitor type differentiation (direct/mind share/authority with border styles)
- [ ] Cluster click → zoom + intelligence panel update
- [ ] Intelligence panel: leaderboard, engines, gaps, winning profile, actions
- [ ] Engine-specific territory toggle (All/ChatGPT/Claude/Perplexity/Google/Gemini)
- [ ] View mode toggle (Citations/Market Share/Authority Type)
- [ ] Gap Intelligence: priority table with opportunity scores and actions
- [ ] Coverage radar: 9 clusters with fill percentages
- [ ] White spaces: zero-presence clusters with action buttons
- [ ] Engine Intelligence: 5 cards + divergence table
- [ ] Embedding Space: D3 scatter with UMAP/t-SNE toggle
- [ ] Proximity Analysis: nearest neighbors on content selection
- [ ] Content DNA: structural signal comparison
- [ ] Authority & Similarity: distance-to-centroid per cluster
- [ ] All interactions smooth (zoom, hover, panel transitions)
- [ ] All brand logos via Google Favicon API
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds