
Phase 2: Gap Analysis Data Endpoints — Implementation Plan
Sprint: front-back-integration
Branch: feat/front-back
Depends on: Phase 1 (complete, 423 tests passing)
Goal: Build 6 GET endpoints + service layer to serve gap analysis data from filesystem artifacts, unblocking all 6 Signal Analysis tabs.
Reviewed by: Codex-equivalent critical review (8 critical issues, 7 warnings addressed below)

Context
The frontend Signal Analysis dashboard has 6 tabs (Overview, Query Intelligence, Structural Signals, Platform Intelligence, Content Briefs, Run History) all consuming ~2,100 lines of hardcoded fixture data in sample-data.ts and webflow-fixtures.ts. The backend has pipeline execution endpoints but no data retrieval endpoints for viewing results. Phase 2 bridges this gap.
All data lives in artifacts/gap_analysis/{slug}/ as JSON files produced by the 8-step pipeline. The service layer reads these files, reshapes them to match frontend type expectations, and caches parsed results.

Critical Design Decisions (from Codex Review)
D1: URL Routing — Separate prefix to avoid {run_id} vs {slug} conflict
The existing gap_analysis.py router uses prefix="/api/v1/gap-analysis" with /{run_id}/status. If new routes used the same prefix with /{slug}/summary, FastAPI would match ramp as a run_id. Solution: New endpoints use a different prefix: prefix="/api/v1/companies/{slug}/gap-analysis", nesting under the companies namespace. This avoids all routing conflicts and is semantically correct (gap data is company-scoped).
D2: Backward compatibility — Old vs new artifact formats
Verified empirically:
* Ramp: has analysis.json (1.8MB) but NO gap_analysis_complete.json. Has 0/45 gaps with content_brief. Structural signals have 11 fields (old format).
* Webflow: has gap_analysis_complete.json (1.6MB). Has content_briefs. Structural signals have 45 fields (new format).
Solution: Fallback chain: try gap_analysis_complete.json first → fall back to analysis.json + gap_report.json. All content_brief access guarded with None checks. Signal averages only computed over fields that actually exist in the data.
D3: platform_citations key casing
Frontend sample data uses lowercase keys: { chatgpt, claude, perplexity, gemini }. Backend engine names are openai, claude, perplexity, gemini. Solution: Map openai → chatgpt (lowercase, matching frontend). Unknown engines pass through with raw name.
D4: Frontend type field mismatches
Frontend Field	Backend Field	Resolution
CitationExemplar.content_type	Not in model	Extract from structural_signals.content_type
StructuralSignals.list_count	list_block_count	Map list_block_count → list_count
ContentBrief.recommended_header_count: number	Tuple[int, int]	Take max of the tuple (frontend uses scalar)
ContentBrief.content_patterns: string[]	Boolean flags	Extract from flags with ≥0.5 threshold
Architecture

NEW FILES:
  api/schemas/gap_data.py          — 20+ Pydantic response models
  api/services/__init__.py         — Package init
  api/services/gap_data_service.py — File loading, caching, 6 service functions + helpers
  api/routers/gap_data.py          — 6 GET endpoints (thin router)
  tests/api/test_gap_data.py       — ~70 tests with fixture builders

MODIFIED FILES:
  api/app.py                       — Register gap_data router (2 lines)

Endpoints
2.1 GET /api/v1/companies/{slug}/gap-analysis/summary
Tab: Overview (SPAScoreHero, GapClassificationCards, ClusterPerformanceHeatmap)
Response model: GapSummaryResponse

class GapSummaryResponse(BaseModel):
    spa_score: SPAScore                    # t_stat, p_value, effect, mean_citation/company_sim
    proximity_stats: ProximityStats        # mean/median citation/company similarity
    classification_counts: GapClassificationCounts  # 4 counts
    cluster_performance: List[ClusterPerformanceRow]  # per-cluster avg_gap, counts, structural rates
    total_queries: int = 0
    total_citations: int = 0
    average_gap: float = 0.0
    executive_summary: str = ""
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
Data sources: gap_report.json + fallback to analysis.json
Mapping:
* spa_score ← spa_results where cluster_name == "all" (first entry)
* classification_counts ← iterate analysis.gaps, count by interpretation field
* cluster_performance ← merge cluster_specs with per-cluster proximity_stats
* executive_summary ← report.executive_summary
* recommendations ← report.recommendations
Error responses: 400 (invalid slug), 404 (no gap_analysis dir for slug)

2.2 GET /api/v1/companies/{slug}/gap-analysis/queries
Tab: Query Intelligence (QueryMasterTable with pagination/filter/sort)
Query params: cluster, classification, search, sort_by (default: gap_score), sort_dir (default: desc), page (default: 1, ge=1), page_size (default: 15, ge=1, le=100)
Response model: QueryListResponse

class QueryRow(BaseModel):
    query_id: str
    query_text: str
    cluster_id: Optional[str] = None
    cluster_name: Optional[str] = None
    gap_score: float = 0.0
    classification: str = "roughly_equal"
    company_sim: float = 0.0
    citation_sim: float = 0.0
    target_words: Dict[str, int] = Field(default_factory=lambda: {"min": 0, "max": 0})
    reading_level: Dict[str, float] = Field(default_factory=lambda: {"min": 0.0, "max": 0.0})
    headers: int = 0
    patterns: List[str] = Field(default_factory=list)
    top_domain: Optional[str] = None
    top_exemplar_sim: float = 0.0
    platform_citations: Dict[str, int] = Field(default_factory=dict)
    content_brief: Optional[QueryContentBrief] = None  # None for old artifacts without briefs
    top_exemplars: List[QueryExemplar] = Field(default_factory=list)

class QueryListResponse(BaseModel):
    queries: List[QueryRow]
    total: int = 0       # total after filtering (not page size)
    page: int = 1
    page_size: int = 15
    total_pages: int = 0
Data sources: gap_analysis_complete.json OR analysis.json (fallback) + enriched_citations.json (for platform_citations)
Key transformations:
* Tuple fields (min, max) → dict {min, max} for JSON/TS friendliness
* content_brief → None if not present on gap (old artifacts like ramp have no briefs)
* patterns extracted from content_brief flags with ≥0.5 threshold. Returns [] if no content_brief.
* platform_citations built by counting enriched citations per (query_id, engine). Keys: chatgpt, claude, perplexity, gemini (lowercase).
* recommended_header_count (tuple) → headers (int): take max of tuple
* Server-side filter → sort → paginate

2.3 GET /api/v1/companies/{slug}/gap-analysis/clusters
Tab: Content Briefs + Overview heatmap
Response model: ClusterListResponse

class ClusterSpecResponse(BaseModel):
    cluster_id: Optional[str] = None
    cluster_name: str
    query_count: int = 0
    citations_analyzed: int = 0
    centroid_distance: Optional[float] = None  # None if centroid data unavailable
    min_similarity_threshold: Optional[float] = None
    word_count_range: Dict[str, int] = Field(default_factory=lambda: {"min": 0, "max": 0})
    required_elements: List[str] = Field(default_factory=list)
    structural_rates: Dict[str, float] = Field(default_factory=dict)
    avg_word_count: float = 0.0
    faq_rate: float = 0.0
    table_rate: float = 0.0
    key_takeaways_rate: float = 0.0
    dominant_content_type: Optional[str] = None
    dominant_authority_type: Optional[str] = None
    exemplar_themes: List[str] = Field(default_factory=list)

class ClusterListResponse(BaseModel):
    clusters: List[ClusterSpecResponse] = Field(default_factory=list)
Data source: gap_analysis_complete.json OR analysis.json → cluster_specs + centroids
Mapping: Merge ClusterContentSpec with CentroidResult.distance by cluster_name. Convert word_count_range: [min, max] → {min, max}. Handle None centroid distances gracefully.

2.4 GET /api/v1/companies/{slug}/gap-analysis/signals
Tab: Structural Signals (SignalCategoryCards, SignalImportanceRanking, ContentPatternMatrix)
Response model: SignalAveragesResponse

class SignalAverageRow(BaseModel):
    signal: str          # display name: "Word Count", "H2 Count", "FAQ Section"
    category: str        # "Text Composition" | "Structural Elements" | "Content Patterns" | "Factual Density"
    citation_avg: float = 0.0
    company_avg: float = 0.0   # 0.0 for now (not captured in s1)
    unit: str = ""
    recommendation: str = ""

class SignalCorrelationRow(BaseModel):
    signal: str
    correlation: float = 0.0
    category: str = ""

class ClusterPatternRow(BaseModel):
    cluster_id: str
    cluster_name: str
    faq: float = 0.0
    definition_opening: float = 0.0
    key_takeaways: float = 0.0
    comparison_table: float = 0.0
    step_by_step: float = 0.0
    research_refs: float = 0.0
    expert_quotes: float = 0.0

class SignalAveragesResponse(BaseModel):
    signals: List[SignalAverageRow] = Field(default_factory=list)
    correlations: List[SignalCorrelationRow] = Field(default_factory=list)
    cluster_patterns: List[ClusterPatternRow] = Field(default_factory=list)
    cluster_fingerprints: Dict[str, Dict[str, float]] = Field(default_factory=dict)
Data sources: enriched_citations.json (structural_signals) + gap_analysis_complete.json OR analysis.json (cluster_specs)
Backward compatibility (old 11-field format):
* Only compute averages for fields that exist in at least one citation's structural_signals
* Use .get(field, None) — skip None values from the average computation
* Old format has: word_count, paragraph_count, header_count, list_item_count, stat_count, citation_count, has_headers, has_lists, has_numbers, authority_type, content_type
* New format adds 34 more fields across 4 categories
* Return only signals that have at least 1 non-None value
Correlations: Pearson correlation between signal values and best_paragraphs[0].similarity. If best_paragraphs is empty (old format), skip that citation in the correlation computation. If fewer than 3 citations have both values, return correlation: 0.0.
Cluster patterns: From cluster_specs for faq_rate, table_rate, key_takeaways_rate. For remaining patterns (definition_opening, comparison_table, step_by_step, research_refs, expert_quotes): compute from enriched_citations grouped by cluster, counting boolean flags.

2.5 GET /api/v1/companies/{slug}/gap-analysis/platforms
Tab: Platform Intelligence (PlatformComparisonDashboard, PlatformAgreementMatrix)
Response model: PlatformListResponse

class PlatformSummaryResponse(BaseModel):
    name: str                    # display name: "ChatGPT", "Claude", "Perplexity", "Gemini"
    total_citations: int = 0
    unique_domains: int = 0
    avg_citation_sim: float = 0.0
    most_cited_domain: Optional[str] = None
    best_cluster: Optional[str] = None
    worst_cluster: Optional[str] = None
    per_cluster: Dict[str, int] = Field(default_factory=dict)

class PlatformListResponse(BaseModel):
    platforms: List[PlatformSummaryResponse] = Field(default_factory=list)
    agreement: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    citation_exclusivity: Dict[str, Dict[str, int]] = Field(default_factory=dict)
Data source: enriched_citations.json
Engine name mapping (for display):

_ENGINE_DISPLAY = {"openai": "ChatGPT", "claude": "Claude", "perplexity": "Perplexity", "gemini": "Gemini"}
# Fallback: unknown engines pass through with title case
Aggregation: Group by engine, handle None engine gracefully (skip), compute counts/domains/similarity per platform. Agreement matrix: Jaccard similarity of URL sets per platform pair. Exclusivity: per-cluster count of URLs cited by 4/3/2/1 platforms.

2.6 GET /api/v1/companies/{slug}/gap-analysis/heatmap
Tab: Overview (ClusterPerformanceHeatmap)
Response model: HeatmapResponse

class HeatmapQuery(BaseModel):
    query_id: str
    query_text: str
    gap_score: float = 0.0
    classification: str = "roughly_equal"

class HeatmapCluster(BaseModel):
    cluster_name: str
    cluster_id: Optional[str] = None
    queries: List[HeatmapQuery] = Field(default_factory=list)
    avg_gap: float = 0.0

class HeatmapResponse(BaseModel):
    clusters: List[HeatmapCluster] = Field(default_factory=list)
    min_gap: float = 0.0
    max_gap: float = 0.0
Data source: gap_analysis_complete.json OR analysis.json → gaps

Service Layer Design
File: api/services/gap_data_service.py
Caching Strategy

_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10

def _load_json_cached(artifacts_root: Path, slug: str, filename: str) -> Optional[Any]:
    """Load JSON file with mtime-based cache invalidation.
    Cache key: (slug, filename). Returns None if file missing."""
Artifact files are immutable between pipeline runs, so mtime check is primarily a safety net for re-runs.
File Loading with Fallback

def _load_analysis_data(artifacts_root: Path, slug: str) -> Dict[str, Any]:
    """Load gap analysis data with fallback chain:
    1. Try gap_analysis_complete.json (has everything: analysis + report + cluster_specs)
    2. Fall back to analysis.json (raw AnalysisResult)
    Returns parsed dict or empty dict if neither exists."""

def _load_report_data(artifacts_root: Path, slug: str) -> Dict[str, Any]:
    """Load report data:
    1. Try gap_report.json (executive_summary, recommendations, proximity_stats, spa_results)
    2. Fall back to gap_analysis_complete.json report section
    Returns parsed dict or empty dict."""
Slug Validation (reused pattern from companies.py)

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

def _validate_slug_dir(artifacts_root: Path, slug: str) -> Path:
    """Validate slug format (400) and check gap_analysis/{slug}/ exists (404).
    Returns the validated path."""
Service Functions
All sync — FastAPI runs sync handlers in threadpool:

def get_summary(artifacts_root: Path, slug: str) -> GapSummaryResponse
def get_queries(artifacts_root, slug, cluster, classification, search, sort_by, sort_dir, page, page_size) -> QueryListResponse
def get_clusters(artifacts_root: Path, slug: str) -> ClusterListResponse
def get_signals(artifacts_root: Path, slug: str) -> SignalAveragesResponse
def get_platforms(artifacts_root: Path, slug: str) -> PlatformListResponse
def get_heatmap(artifacts_root: Path, slug: str) -> HeatmapResponse
Helper Functions

def _build_platform_index(enriched: List[Dict]) -> Dict[str, Dict[str, int]]:
    """query_id -> {engine_key -> count}. Engine keys are lowercase frontend keys."""

def _extract_patterns(content_brief: Optional[Dict]) -> List[str]:
    """Extract pattern names from boolean flags ≥ 0.5. Returns [] if content_brief is None."""

def _compute_signal_averages(enriched: List[Dict]) -> List[SignalAverageRow]:
    """Mean structural signals. Only includes fields present in data (handles old 11-field format)."""

def _compute_signal_correlations(enriched: List[Dict]) -> List[SignalCorrelationRow]:
    """Pearson correlation of each signal with best_paragraphs[0].similarity.
    Skips citations with empty best_paragraphs. Returns 0.0 if < 3 data points."""

def _compute_cluster_patterns(enriched: List[Dict], cluster_specs: List[Dict]) -> List[ClusterPatternRow]:
    """Per-cluster content pattern rates. Merges cluster_specs data with enriched_citations aggregation."""

def _compute_cluster_fingerprints(cluster_specs: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Normalized (0-1) radar chart data per cluster. Normalizes across all clusters per signal."""

def _compute_platform_agreement(enriched: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Jaccard similarity of URL sets between each platform pair."""

def _compute_citation_exclusivity(enriched: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Per-cluster: count URLs cited by all_4, three, two, one platforms."""

_ENGINE_DISPLAY = {"openai": "ChatGPT", "claude": "Claude", "perplexity": "Perplexity", "gemini": "Gemini"}
_ENGINE_KEYS = {"openai": "chatgpt", "claude": "claude", "perplexity": "perplexity", "gemini": "gemini"}

def _map_engine_display(engine: Optional[str]) -> str:
    """Map engine name to display name. Unknown engines → title case. None → 'Unknown'."""

def _map_engine_key(engine: Optional[str]) -> str:
    """Map engine name to lowercase frontend key. None → 'unknown'."""

Data Source → File → Endpoint Mapping
Artifact File	Size	Endpoints	Fallback
gap_analysis_complete.json	~1.6 MB	2.1, 2.2, 2.3, 2.6	analysis.json (1.8 MB)
gap_report.json	~588 KB	2.1	gap_analysis_complete.json report section
enriched_citations.json	~20 MB	2.2, 2.4, 2.5	None (endpoints return empty data)
generation_spec.json	~10 KB	2.3 (fallback)	None
Router
File: api/routers/gap_data.py

router = APIRouter(
    prefix="/api/v1/companies/{slug}/gap-analysis",
    tags=["gap-data"],
)
Nested under /companies/{slug}/ to avoid conflict with existing /api/v1/gap-analysis/{run_id}/status. Same slug validation pattern as companies.py.
Registration in api/app.py — 2 lines:

from api.routers import gap_data
app.include_router(gap_data.router)

Test Strategy
Fixture Builders
Two fixture variants to test backward compatibility:

def _make_complete_new_format(gaps=5, clusters=2, with_briefs=True) -> Dict:
    """Webflow-style: gap_analysis_complete.json with 45-field structural signals and content_briefs."""

def _make_analysis_old_format(gaps=5, clusters=2) -> Dict:
    """Ramp-style: analysis.json with 11-field structural signals, no content_briefs."""

def _make_enriched(count=10, engines=None, with_similarity=True) -> List[Dict]:
    """Enriched citations with configurable engines and best_paragraphs."""

def _make_gap_report(summary="Test summary", recommendations=2) -> Dict:
    """gap_report.json with executive_summary, recommendations, proximity_stats, spa_results."""
Test Classes (~70 tests)
Class	Tests	Key Scenarios
TestGapSummary	~12	SPA score, proximity, classification counts, cluster perf, 404/400, missing files, empty gaps
TestGapQueries	~16	Pagination, filter by cluster/classification/search, sort asc/desc, content_brief None handling, exemplars, platform_citations, page_size validation
TestGapClusters	~8	Cluster list, centroid merge, word_count_range format, None centroid, expanded fields, old format fallback
TestGapSignals	~10	Signal averages (new format), old format (11 fields only), correlations, cluster patterns, cluster fingerprints, empty enriched_citations
TestGapPlatforms	~10	Platform list, per_cluster, unique domains, agreement matrix, exclusivity, None engine handling, engine name mapping
TestGapHeatmap	~6	Structure, cluster grouping, min/max gap, empty gaps, old format
TestBackwardCompat	~5	Ramp-like old format: analysis.json fallback, no content_briefs, 11-field signals
TestCaching	~3	Cache hit, mtime invalidation, max entries
Implementation Order (TDD)
Task 1: Response Models (api/schemas/gap_data.py) — ~30 min
* All 20+ Pydantic models with defaults on every field
* Matches frontend TypeScript types exactly (with documented field mappings from D4)
Task 2: Service Layer (api/services/gap_data_service.py) — ~2.5 hours
* Create api/services/__init__.py
* Implement in order:
    1. _load_json_cached(), _validate_slug_dir(), _load_analysis_data(), _load_report_data() — foundation + fallback chain
    2. get_summary() — reads report + analysis, extracts SPA/proximity/classification/cluster perf
    3. get_heatmap() — groups gaps by cluster
    4. get_clusters() — merges cluster_specs + centroids
    5. get_queries() — joins gaps + enriched_citations, handles None content_brief, filter/sort/paginate
    6. get_signals() — aggregation with old-format awareness, correlations, cluster patterns, fingerprints
    7. get_platforms() — aggregation + Jaccard + exclusivity
Task 3: Router + Registration (api/routers/gap_data.py, api/app.py) — ~20 min
* Thin router, slug validation, query params with FastAPI Query() constraints
* Register in app.py
Task 4: Tests (tests/api/test_gap_data.py) — ~2 hours
* Fixture builders (both old and new format)
* ~70 tests across 8 test classes
* Covers every endpoint + backward compatibility + caching
Task 5: Integration Verification — ~20 min
* pytest tests/ -v — all 423+ tests pass (no regressions)
* Manual smoke test with real artifacts

Risk Assessment
Risk	Severity	Mitigation
Routing conflict /{run_id} vs /{slug}	Resolved	New endpoints under /companies/{slug}/gap-analysis/ (separate prefix)
Old artifact format (no content_brief, 11 signals)	Resolved	Fallback chain + None guards + only compute present fields
enriched_citations.json memory (~60 MB parsed per slug)	Low	Cap cache at 10 entries, FIFO eviction. Single-server for now.
Frontend field mismatches (content_type, list_count, headers)	Resolved	Explicit field mapping documented in D4
platform_citations key casing	Resolved	Lowercase keys (chatgpt not ChatGPT) matching frontend
Company structural signals unavailable	Medium	company_avg: 0.0 with recommendation text. Deferred to future s1 enhancement.
None engine on enriched citations	Resolved	Skip citations with engine=None in platform aggregation
Correlation computation with empty best_paragraphs	Resolved	Skip those citations, return 0.0 if < 3 data points
Critical Files Reference
File	Role
core/models/gap_analysis.py	Source Pydantic models (AnalysisResult, QueryGap, EnrichedCitation, StructuralSignals, ClusterContentSpec, GapContentBrief, CitationExemplar, SpaResult, CentroidResult)
api/routers/companies.py	Reference pattern for slug validation, artifact scanning, response building
api/dependencies.py	DI pattern: get_artifacts_root(), get_task_store()
api/schemas/common.py	Existing response model patterns
tests/api/conftest.py	Test client fixtures, artifacts_root tmp_path setup
frontend-dashboard/src/types/gap-analysis.ts	Frontend TypeScript interfaces to match
frontend-dashboard/src/app/(dashboard)/signal-analysis/data/sample-data.ts	Definitive frontend data shapes: QueryData, SignalAverageRow, PlatformSummary, etc.
core/gap_analysis/steps/s8_generate_report.py	Understand what gap_report.json / gap_analysis_complete.json contain
Verification Plan
1. Unit tests: pytest tests/api/test_gap_data.py -v — all ~70 tests pass
2. Full regression: pytest tests/ -v — all 423+ tests pass (no regressions)
3. Manual smoke test: Start server, call each endpoint with both webflow (new format) and ramp (old format) slugs, verify JSON shape
4. Error handling: Test with invalid slug (400), missing slug dir (404), partial artifacts (graceful degradation)
5. Cache verification: Call same endpoint twice, verify second call is faster (mtime cache hit)
