

ARCHITECTURE DESIGN DOCUMENT

**Topic Discovery Module**

*Strategic Content Planning Layer for the Deep Presence Platform*

Version 0.1  —  March 2026

Deep Presence  •  Internal Engineering Document

**Status: Draft  •  For Review**

# **1\. Executive Summary**

The Topic Discovery Module is a strategic planning layer that answers the upstream question every content operation faces: what is the complete universe of content we could produce, and how do we systematically choose what to produce next?

Unlike the Gap Analysis pipeline (which answers “where are we losing right now?” by measuring semantic proximity against live LLM citations) and the Content Engine (which answers “how do we produce good content?”), the Topic Discovery Module produces an exhaustive, hierarchically-organized map of all possible content opportunities for a client, segmented by domain taxonomy, buyer journey stage, search intent, and audience segment.

The module runs once after the Research Pipeline finalizes its three core artifacts (Company Profile, Audience Personas, Voice Style Guide). Its output is a persistent, versioned planning artifact that serves as the authoritative source for content prioritization. The taxonomy can be incrementally refined through human editing over time as the client’s market position or strategy evolves.

| Core Value Proposition *Transforms content planning from ad-hoc topic brainstorming into systematic coverage mapping.* *Provides mathematically-grounded exhaustiveness guarantees via Multi-Source Capture-Recapture.* *Integrates with the Gap Analysis embedding space for visual strategic planning.* *Enables weekly content cycle planning with target projection overlays.* |
| :---- |

# **2\. Module Position in the Platform**

The Topic Discovery Module occupies a specific place in the Deep Presence pipeline dependency chain. Understanding this position is critical for integration design.

## **2.1 Dependency Chain**

| Stage | Module | Produces |
| :---- | :---- | :---- |
| Stage 1 | Research Pipeline | Company Profile, Audience Personas, Voice Style Guide |
| Stage 2 | Topic Discovery Module | Domain Taxonomy Tree, Topic Assignment Matrix, Target Embedding Set |
| Stage 3 | Gap Analysis Pipeline | Semantic proximity scores, citation patterns, embedding projections |
| Stage 4 | Content Engine | Optimized content pieces guided by all upstream artifacts |

The Topic Discovery Module consumes the three research artifacts as input context and produces a taxonomy that downstream modules reference. The Gap Analysis pipeline’s query set should eventually be derived from the taxonomy (rather than generated independently), creating a tight feedback loop between strategic planning and empirical measurement.

## **2.2 Trigger & Lifecycle**

**Initial Generation:** Automatically triggered after the Research Pipeline completes and all three artifacts (Company Profile, Audience Personas, Voice Style Guide) are finalized and HITL-approved.

**Incremental Refinement:** On-demand. The marketing team or account manager can trigger a re-generation or partial update when the client’s strategy shifts, new product lines launch, or market conditions change. The system also allows manual addition, deletion, and restructuring of taxonomy branches at any time without triggering a full pipeline re-run.

**Versioning:** Each generation or significant edit creates a new version. Previous versions are retained for comparison and rollback.

# **3\. Core Concepts & Terminology**

| Term | Definition |
| :---- | :---- |
| Domain | The primary business/market space the client operates in. For Cursor, this would be “software development.” A client has exactly one domain. |
| Subdomain | A distinct thematic area within the domain. For Cursor: “agentic development,” “tab completion,” “front-end design mode,” “enterprise deployment,” etc. The exhaustive set of subdomains is the primary output of the Taxonomy Engine. |
| Topic Assignment | A specific content opportunity within a subdomain, parameterized by buyer stage, intent type, and audience segment. Represents a concrete piece of content that could be produced. Roughly equivalent to a query a user might ask an LLM platform. |
| Buyer Stage | Position in the purchase funnel: TOFU (awareness/education), MOFU (consideration/evaluation), BOFU (decision/purchase). Each subdomain generates topic assignments across all three stages. |
| Intent Type | The searcher’s underlying goal: Informational, Navigational, Commercial Investigation, or Transactional. Crosses with buyer stage to produce distinct query patterns. |
| Audience Segment | Who the content targets. Two dimensions: persona type (individual role, e.g., “senior developer”) and group type (team-level, e.g., “engineering team,” “product team”). Derived from the Audience Persona artifacts. |
| Taxonomy Tree | The hierarchical structure: Domain → Subdomains → Topic Clusters. The persistent strategic planning artifact. |
| Coverage Score | A mathematically-derived estimate (via Capture-Recapture) of what percentage of the total possible subdomain space has been mapped. Presented to the user alongside the taxonomy. |
| Target Embedding Set | Precomputed embeddings for topic assignments that can be projected into the Gap Analysis UMAP/t-SNE space, enabling visual strategic planning overlays. |

# **4\. Architecture Overview**

The Topic Discovery Module is structured as a 5-stage LangGraph pipeline with three HITL approval gates. The pipeline follows the platform’s established pattern of deterministic orchestration with LLM calls at well-defined points.

## **4.1 Pipeline Stages**

| Stage | Name | Input | Output |
| :---- | :---- | :---- | :---- |
| S1 | Multi-Source Subdomain Generation | Company Profile, Audience Personas, Style Guide, Competitor sitemaps (if available) | 4+ independent subdomain lists |
| S2 | Exhaustiveness Evaluation & Merge | Independent subdomain lists from S1 | Unified subdomain set \+ coverage confidence score |
| ─ | **HITL-1: Taxonomy Approval** | Merged taxonomy tree \+ coverage score | Approved/modified taxonomy |
| S3 | Dimensionality Expansion | Approved subdomains \+ Personas \+ Buyer stages | Full Topic Assignment Matrix |
| ─ | **HITL-2: Matrix Review** | Topic Assignment Matrix with priority scores | Approved/modified matrix |
| S4 | Embedding Generation | Approved topic assignments | Target Embedding Set (vector per topic) |
| S5 | Artifact Persistence & Scoring | All upstream outputs | Versioned taxonomy artifact, integration-ready data |
| ─ | **HITL-3: Final Sign-off** | Complete taxonomy with embeddings \+ coverage metrics | Finalized discovery artifact |

Each stage is implemented as a LangGraph node. HITL gates use LangGraph’s interrupt() mechanism, consistent with the Research Pipeline and Content Engine v1.3 patterns.

# **5\. Layer 1: Taxonomy Engine (Stages S1–S2)**

The Taxonomy Engine is responsible for producing an exhaustive mapping of all subdomains within the client’s domain. Exhaustiveness is the critical requirement — missing a subdomain means an entire content vertical goes unaddressed.

## **5.1 Stage S1: Multi-Source Subdomain Generation**

Four independent generation strategies run in parallel. Independence between sources is critical for the Capture-Recapture math to hold.

### **Source A — Company Profile Brainstorm**

An LLM call seeded with the Company Profile artifact. The prompt instructs the model to decompose the client’s domain into every distinct thematic area the company’s products, services, or expertise could address. This source thinks from the company’s perspective: “what do we do?”

### **Source B — Audience Persona Brainstorm**

An LLM call seeded with the Audience Persona artifacts. For each persona, the prompt asks: “what distinct problem areas, workflows, and decision contexts does this persona encounter that relate to the client’s domain?” This source thinks from the customer’s perspective: “what do they need?” The outputs across all personas are merged into a single list for this source.

### **Source C — Competitor Sitemap Extraction**

An empirical (non-generative) source. If competitor sitemaps are available from the Site Audit or Gap Analysis pipeline, this step extracts content categories by analyzing URL path structures and page title patterns. An LLM call then normalizes these into subdomain labels consistent with the other sources. This source is structurally independent from LLM brainstorming because it’s grounded in real published content.

### **Source D — Adversarial Diversity Pass**

A specialized LLM call designed to counter Zipf bias (the tendency for LLMs to over-represent common subdomains and systematically miss niche ones). The prompt instructs: “What subdomains would a specialist in \[specific niche\] care about that a generalist would overlook?” This runs multiple sub-passes with different specialist lenses (e.g., accessibility specialist, regulatory compliance specialist, enterprise procurement specialist). This is the most important source for catching long-tail subdomains.

| Design Note: Source Independence *Sources A and B approach the domain from genuinely different angles (supply-side vs. demand-side).* *Source C is empirical, not generative — structurally independent from LLM outputs.* *Source D uses adversarial prompting to break the frequency bias shared by A and B.* *This diversity is what makes Capture-Recapture estimates mathematically valid.* |
| :---- |

### **Iterative Expansion Rounds**

After the initial parallel generation, each source runs 3–5 iterative expansion rounds. In each round, the LLM is prompted: “Given the subdomains already discovered, what additional subdomains have been missed?” The previously discovered subdomains are provided as context. Singletons (subdomains appearing in only one round) are tracked for the Chao1 estimator.

## **5.2 Stage S2: Exhaustiveness Evaluation & Merge**

This stage performs three operations: deduplication, coverage estimation, and hierarchy construction.

### **5.2.1 Deduplication via Semantic Matching**

Subdomains from all four sources are embedded (using the same embedding model as the Gap Analysis pipeline). Pairs with cosine similarity above a configurable threshold (default 0.85) are flagged as duplicates. An LLM arbitration call selects the best canonical label for each duplicate cluster, preserving the source provenance metadata.

### **5.2.2 Coverage Estimation (Multi-Source Capture-Recapture)**

Pairwise Capture-Recapture estimates are computed for all source pairs. For any two sources with overlap:

| Capture-Recapture Formula *Estimated Total \= (|Source X| × |Source Y|) / |Overlap(X, Y)|* *Example: Source A finds 80, Source B finds 70, with 50 overlapping.* *Estimated total \= (80 × 70\) / 50 \= 112\. With 100 unique found, \~12 remain undiscovered.* |
| :---- |

The module computes pairwise estimates for all six source pairs (A-B, A-C, A-D, B-C, B-D, C-D) and triangulates using the median estimate to reduce variance from any single pair. Additionally, the Chao1 lower-bound estimator and Sample Coverage metric are computed from the iterative expansion round data:

* **Chao1 lower bound:** Provides a minimum estimate of total subdomains based on singleton frequency.

* **Sample Coverage (Ĉ \= 1 − f₁/N):** When this crosses 0.95, the remaining undiscovered subdomains represent less than 5% of total domain mass.

* **Convergence check:** If Capture-Recapture, Chao1, and Sample Coverage all agree within a tolerance band, confidence is high.

The coverage score is presented to the user at HITL-1 as a human-readable metric, e.g., “Estimated 94% domain coverage, approximately 8–12 potential undiscovered subdomains remaining.”

### **5.2.3 Hierarchy Construction**

The flat list of deduplicated subdomains is organized into a tree structure. An LLM call groups related subdomains under parent categories where natural hierarchies exist (e.g., “Enterprise Features” might be a parent containing “SSO Integration,” “Team Management,” “Audit Logging”). The result is a 2–3 level tree: Domain → Subdomain Groups (optional) → Subdomains.

Each subdomain node carries metadata: source provenance (which sources discovered it), confidence level (appeared in 1/4 sources vs. 4/4), and a brief description generated by the LLM.

## **5.3 HITL-1: Taxonomy Approval**

The taxonomy tree and coverage metrics are presented to the user. The user can:

* **Approve:** Accept the taxonomy as-is and proceed to dimensionality expansion.

* **Modify:** Add new subdomains, delete irrelevant ones, rename labels, or restructure the hierarchy. The system accepts these edits and re-computes coverage metrics.

* **Retry with feedback:** Provide natural-language feedback (e.g., “You’re missing the entire regulatory compliance vertical”) that triggers a targeted re-generation pass focused on the feedback area.

# **6\. Layer 2: Dimensionality Matrix (Stage S3)**

For each approved subdomain, Stage S3 expands the taxonomy across three orthogonal dimensions to produce the full Topic Assignment Matrix.

## **6.1 The Three Dimensions**

| Dimension | Values | Design Rationale |
| :---- | :---- | :---- |
| Buyer Stage | TOFU (awareness/education), MOFU (consideration/evaluation), BOFU (decision/purchase) | Different content formats, depth levels, and CTAs are appropriate at each stage. |
| Intent Type | Informational (“what is X”), Commercial (“best X tools”), Navigational (“X vs Y”), Transactional (“X pricing/setup”) | Determines the query pattern and content structure needed. |
| Audience Segment | Individual personas (from Persona artifacts) \+ group/team-level targets (engineering team, product team, design team, etc.) | The same subdomain requires different framing for different audiences. |

## **6.2 Expansion Strategy**

The expansion is not a blind cartesian product. The module uses a two-pass approach:

1. **Relevance Filtering:** For each subdomain, an LLM call determines which dimension combinations are actually meaningful. Not every subdomain has relevant BOFU/Transactional content; not every subdomain targets every persona. The LLM returns a relevance matrix marking each cell as “relevant,” “marginal,” or “irrelevant.”

2. **Topic Assignment Generation:** For each “relevant” cell, the LLM generates 2–5 specific topic assignments (concrete content opportunities phrased as queries a user might ask). These are the atomic units of the planning system.

This approach avoids the combinatorial explosion problem. A naive 15 subdomains × 3 buyer stages × 4 intents × 5 personas \= 900 cells, but after relevance filtering, typically 30–50% of cells survive, and each contains 2–5 topic assignments. The result is a prioritized set of 200–600 concrete topic assignments rather than an unmanageable 4,500-cell matrix.

## **6.3 Priority Scoring**

Each topic assignment receives a composite priority score computed from:

* **Strategic alignment:** How closely this topic aligns with the client’s current business priorities (extracted from Company Profile).

* **Audience coverage:** Whether this persona/group segment is underserved in the current matrix (balancing coverage across segments).

* **Funnel balance:** Maintaining healthy distribution across TOFU/MOFU/BOFU (avoiding over-indexing on any stage).

* **Competitive signal (if available):** If Gap Analysis data exists, topics in high-gap areas receive priority boosts.

* **Content format feasibility:** Some topics naturally lend themselves to high-impact formats (comprehensive guides, comparison pages) that tend to get cited more by LLM platforms.

## **6.4 HITL-2: Matrix Review**

The complete Topic Assignment Matrix is presented with priority scores, grouped by subdomain. The user can approve the matrix, adjust priorities, add/remove specific topic assignments, or flag subdomains for deeper expansion. This is the checkpoint where the client’s marketing team can inject their domain expertise and near-term strategic priorities.

# **7\. Layer 3: Embedding Space Integration (Stages S4–S5)**

This layer bridges the Topic Discovery Module with the Gap Analysis visualization system, enabling the “closed-loop strategic planning” workflow.

## **7.1 Stage S4: Embedding Generation**

Each approved topic assignment is embedded using the same embedding model and dimensionality as the Gap Analysis pipeline (currently text-embedding-3-small, 1536 dimensions). The embedding is generated from a composite text representation:

| Embedding Input Template *\[Subdomain\]: {subdomain\_name}* *\[Buyer Stage\]: {buyer\_stage} | \[Intent\]: {intent\_type}* *\[Audience\]: {persona\_or\_group}* *\[Topic\]: {topic\_assignment\_text}* |
| :---- |

This structured representation ensures the embedding captures not just the topic semantics but the dimensional context (who it’s for, where in the funnel, what intent it serves).

## **7.2 Projection into Gap Analysis Space**

The critical technical requirement: topic embeddings must be projectable into the same 2D space as the Gap Analysis UMAP/t-SNE scatter plot without recomputing the entire projection.

Two approaches are supported:

1. **UMAP transform() (preferred):** The Gap Analysis pipeline’s trained UMAP model is persisted as a serialized artifact. New topic embeddings are projected into the existing learned space via UMAP’s transform() method. This preserves the spatial relationships of the original gap analysis points while placing new targets in semantically consistent positions.

2. **Nearest-neighbor interpolation (fallback):** If the UMAP model is unavailable (e.g., gap analysis hasn’t run yet), topic embeddings are positioned in a standalone 2D projection. When gap analysis subsequently runs, a re-projection merges both sets.

## **7.3 The Weekly Planning Overlay**

This is the operational interface where the Topic Discovery Module’s strategic map meets the Gap Analysis’s empirical data in a single visualization.

The workflow for the marketing team’s weekly content planning cycle:

1. **Selection:** The team selects which subdomains and/or audience segments they want to target this week (e.g., “front-end development for designers”).

2. **Projection:** The topic assignments matching that selection are projected into the Gap Analysis embedding space as distinct markers (e.g., star symbols in a different color from the existing query/citation/company points).

3. **Visual Analysis:** The team can now see: (a) where their target content would land semantically relative to the current gap analysis landscape, (b) which targets fall in high-gap regions (biggest opportunities), (c) which targets cluster near existing company content (optimization vs. net-new), and (d) which targets are in dense citation-rich zones (competitive but high-value).

4. **Handoff to Content Engine:** Selected topic assignments become the input to the Content Engine’s Strategic Planner, replacing or supplementing the current scorecard-based topic selection.

| Integration Note *The weekly planning overlay is a frontend visualization feature. The backend provides* *an API endpoint that accepts a list of topic assignment IDs and returns their 2D coordinates* *in the gap analysis projection space, along with the full gap analysis point set for rendering.* |
| :---- |

# **8\. Exhaustiveness Evaluation Framework**

Exhaustiveness is the differentiating property of this module. Any LLM can brainstorm topics; the value is in the mathematical confidence that the brainstorm is complete. This section details the statistical framework.

## **8.1 Multi-Source Capture-Recapture**

The classical ecological method adapted for LLM-generated taxonomies. Each of the four generation sources (S1 Sources A–D) acts as an independent “capture” pass. The overlap between any two passes reveals the total population size:

| Metric | Formula | Interpretation |
| :---- | :---- | :---- |
| Estimated Total (N̂) | N̂ \= (n₁ × n₂) / m | Where n₁ and n₂ are counts from two sources, m is their overlap count |
| Chao1 Lower Bound | S\_obs \+ (f₁² / 2f₂) | Where f₁ \= singletons, f₂ \= doubletons in iterative rounds |
| Sample Coverage | Ĉ \= 1 − (f₁ / N) | Proportion of total domain mass represented by discovered subdomains |
| Coverage Target | Ĉ ≥ 0.95 | Remaining undiscovered subdomains represent \<5% of domain mass |

## **8.2 Confidence Reporting**

The system presents three convergence signals to the user at HITL-1:

1. **Capture-Recapture estimate:** Median of all pairwise estimates ± range. Example: “Estimated 110–125 total subdomains (median: 118).”

2. **Chao1 lower bound:** The minimum plausible total. Example: “At least 108 subdomains exist.”

3. **Sample coverage:** The completeness percentage. Example: “94.2% estimated coverage.”

When all three metrics converge (e.g., CR says \~118 total, Chao1 says ≥108, coverage is 94%, and we’ve found 111), the user gets a clear and credible picture of taxonomy completeness.

## **8.3 Handling the Zipf Bias**

LLMs exhibit Zipf-distributed generation: common subdomains are reliably surfaced while niche ones are systematically missed. The module addresses this through:

* **Source D (Adversarial Diversity):** Purpose-built to surface long-tail subdomains through specialist-lens prompting.

* **Iterative expansion rounds:** Progressive prompting (“what did you miss?”) with singleton tracking.

* **Empirical grounding (Source C):** Competitor sitemaps surface subdomains that exist in the real market regardless of LLM training data frequency.

* **HITL correction:** Domain experts often know niche subdomains that neither LLMs nor competitors have surfaced.

# **9\. Data Models**

The following data models represent the core entities of the Topic Discovery Module. These extend the existing database schema (which already has placeholder TopicDiscoveryModel and DiscoveredTopicModel tables) with the full structural richness the module requires.

## **9.1 Taxonomy Tree**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | UUID | Primary key |
| discovery\_id | UUID (FK) | Parent TopicDiscovery run |
| domain\_name | String | The client’s primary domain label |
| version | Integer | Auto-incrementing version number |
| coverage\_score | Float | Sample coverage metric (0–1) |
| capture\_recapture\_est | JSONB | Full CR estimates: pairwise, median, range |
| chao1\_lower\_bound | Float | Chao1 minimum estimate |
| status | Enum | draft / hitl\_pending / approved / archived |
| created\_at | DateTime | Timestamp of creation |

## **9.2 Subdomain Node**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | UUID | Primary key |
| taxonomy\_id | UUID (FK) | Parent taxonomy tree |
| parent\_id | UUID (FK, nullable) | Parent subdomain (for nested hierarchy) |
| name | String | Human-readable subdomain label |
| description | Text | LLM-generated brief description |
| source\_provenance | JSONB | Which sources discovered this: {A: true, B: true, C: false, D: true} |
| confidence | Float | Proportion of sources that discovered this (0.25–1.0) |
| is\_manually\_added | Boolean | True if added by human via HITL edit |
| sort\_order | Integer | Display ordering within parent |
| embedding | Vector(1536) | Subdomain-level embedding for clustering |

## **9.3 Topic Assignment**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | UUID | Primary key |
| subdomain\_id | UUID (FK) | Parent subdomain |
| topic\_text | Text | The concrete topic/query (e.g., “Best front-end vibe coding tools for designers in 2026”) |
| buyer\_stage | Enum | TOFU / MOFU / BOFU |
| intent\_type | Enum | informational / commercial / navigational / transactional |
| audience\_segment\_type | Enum | individual\_persona / team\_group |
| audience\_segment\_label | String | e.g., “senior developer” or “product team” |
| priority\_score | Float | Composite priority (0–1) |
| priority\_factors | JSONB | Breakdown: {strategic: 0.8, audience\_coverage: 0.6, ...} |
| status | Enum | not\_started / in\_gap\_analysis / content\_produced / published |
| content\_piece\_id | UUID (FK, nullable) | Link to produced content (when status advances) |
| embedding | Vector(1536) | Target embedding for projection |
| is\_manually\_added | Boolean | True if added by human |
| relevance\_cell | Enum | relevant / marginal / irrelevant (from dimensionality expansion) |

# **10\. Integration Points**

## **10.1 Research Pipeline → Topic Discovery (Input)**

The Topic Discovery Module is triggered after the Research Pipeline’s three artifacts are HITL-approved. It receives:

* Company Profile artifact (full JSON/text)

* Audience Persona artifacts (all 3–4 personas)

* Voice Style Guide artifact (for tone-consistent topic phrasing)

These are read-only inputs. The Topic Discovery Module never modifies research artifacts.

## **10.2 Topic Discovery → Gap Analysis (Bidirectional)**

Forward flow: The Gap Analysis pipeline’s query set should eventually be derived from the Topic Assignment Matrix, replacing the current independent query generation. This ensures gap analysis measures coverage against the strategic map.

Reverse flow: If Gap Analysis has already run, its gap scores can be used to boost priority scoring in Stage S3. Additionally, the trained UMAP model from Gap Analysis S7 (visualize step) is consumed by Stage S4 for embedding projection.

## **10.3 Topic Discovery → Content Engine (Output)**

Selected topic assignments flow into the Content Engine as the authoritative “what to write” signal. This can replace or supplement the Strategic Planner’s current scorecard-based topic selection. Each topic assignment carries its full dimensional context (subdomain, buyer stage, intent, audience) which informs the Brief Builder and Content Workers.

## **10.4 Topic Discovery → Frontend (Visualization)**

The API surface exposes the taxonomy tree for browsable navigation, the topic assignment matrix for filtering/sorting, embedding coordinates for the planning overlay scatter plot, and coverage metrics for the confidence display. The weekly planning overlay is a frontend-driven workflow that calls backend APIs for topic selection and projection.

# **11\. API Surface (Planned)**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| POST | /api/v1/companies/{slug}/topic-discovery/run | Trigger a new discovery run |
| GET | /api/v1/companies/{slug}/topic-discovery/taxonomy | Get current taxonomy tree with coverage metrics |
| PATCH | /api/v1/companies/{slug}/topic-discovery/taxonomy/nodes/{id} | Edit a subdomain node (rename, move, delete) |
| POST | /api/v1/companies/{slug}/topic-discovery/taxonomy/nodes | Add a new subdomain node (manual addition) |
| GET | /api/v1/companies/{slug}/topic-discovery/matrix | Get topic assignment matrix with filters |
| PATCH | /api/v1/companies/{slug}/topic-discovery/assignments/{id} | Edit a topic assignment (priority, status, text) |
| POST | /api/v1/companies/{slug}/topic-discovery/assignments | Add a new topic assignment (manual) |
| POST | /api/v1/companies/{slug}/topic-discovery/project | Project selected assignments into gap analysis space |
| GET | /api/v1/companies/{slug}/topic-discovery/coverage | Get exhaustiveness metrics and confidence scores |
| GET | /api/v1/companies/{slug}/topic-discovery/versions | List taxonomy versions with diffs |

# **12\. Open Questions & Future Considerations**

## **12.1 Gap Analysis Query Derivation**

Currently, the Gap Analysis pipeline generates its own 100–200 queries independently. The long-term vision is for these to be sampled from the Topic Assignment Matrix. The open question is the transition strategy: do we run both in parallel for a validation period, or cut over when the Topic Discovery Module is mature enough?

## **12.2 Taxonomy Drift Detection**

Markets evolve. A taxonomy generated in Q1 may miss subdomains that emerge by Q3. Should the system periodically re-run Source C (competitor sitemap extraction) and Source D (adversarial diversity) against the existing taxonomy to detect drift? This could be a lightweight “health check” that flags when the taxonomy may need a refresh.

## **12.3 Content-to-Topic Linkage**

When the Content Engine produces a piece targeting a specific topic assignment, the assignment’s status should advance (not\_started → content\_produced → published). The mechanics of this linkage — automatic via embedding similarity vs. explicit via the Content Engine passing the assignment ID — need to be specified in the implementation spec.

## **12.4 Multi-Product Support**

Some clients have multiple products or business lines. The current schema supports a product\_id foreign key on the TopicDiscovery model. Should each product have its own taxonomy, or should there be a shared domain taxonomy with product-specific overlays? This has UX implications for the planning interface.

## **12.5 Embedding Model Consistency**

The Topic Discovery embeddings must use the same model as Gap Analysis for projection compatibility. If the embedding model is upgraded across the platform, all topic embeddings need re-generation. The versioning system should track which embedding model version was used.

*End of Architecture Design Document  —  Version 0.1*