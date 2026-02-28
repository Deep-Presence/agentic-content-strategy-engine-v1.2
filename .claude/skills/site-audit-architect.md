# Site Audit — Architect Specification

## Models to Create (core/models/site_audit.py)

Study `core/models/gap_analysis.py` for the pattern. Every field must have a default value. Use `Field(default=...)` or `Field(default_factory=...)`.

### Enums

```python
class AuditDimension(str, Enum):
    crawlability = "crawlability"
    performance = "performance"
    on_page_seo = "on_page_seo"
    extractability = "extractability"      # AEO-specific
    schema_markup = "schema_markup"
    eeat = "eeat"
    freshness = "freshness"
    security = "security"

class AuditCheckSeverity(str, Enum):
    critical = "critical"     # Penalty: 10 pts
    high = "high"             # Penalty: 5 pts
    medium = "medium"         # Penalty: 2 pts
    low = "low"               # Penalty: 1 pt
    info = "info"             # Penalty: 0 pts
```

### Core Models

**SiteAuditInput** — Pipeline input (required fields OK here since this is an input):
- company_name: str
- domain: str
- company_slug: Optional[str] = None
- product_slug: Optional[str] = None
- max_pages: int = 200
- max_depth: int = 4
- check_core_web_vitals: bool = True
- check_schema_validation: bool = True
- check_ai_bot_access: bool = True

**AuditFinding** — Individual check result:
- finding_type: str = "" (e.g., "missing_title", "broken_h1_hierarchy")
- dimension: AuditDimension = AuditDimension.crawlability
- severity: AuditCheckSeverity = AuditCheckSeverity.info
- message: str = ""
- recommendation: str = ""
- url: str = ""
- details: dict[str, Any] = Field(default_factory=dict)

**SchemaDetectionResult** — Per-page schema analysis:
- has_schema: bool = False
- schema_types: list[str] = Field(default_factory=list) (e.g., ["Article", "FAQPage"])
- raw_jsonld_blocks: list[dict[str, Any]] = Field(default_factory=list)
- validation_errors: list[str] = Field(default_factory=list)
- inferred_page_type: str = "unknown"

**AEOReadinessResult** — Per-page AEO score:
- snippet_readiness_score: float = 0.0 (0-100)
- question_heading_ratio: float = 0.0
- quick_answer_hook_count: int = 0
- self_contained_paragraph_ratio: float = 0.0
- avg_paragraph_word_count: float = 0.0
- content_patterns: dict[str, bool] = Field(default_factory=dict) (faq_section, definition_opening, key_takeaways, comparison_table, numbered_steps, toc)

**PageAuditResult** — Per-page comprehensive result (~50 fields organized in groups):
- url: str = ""
- status_code: int = 0
- crawl_depth: int = 0
- redirect_url: Optional[str] = None
- title: str = ""
- title_length: int = 0
- meta_description: str = ""
- meta_description_length: int = 0
- h1_count: int = 0
- h1_text: str = ""
- heading_hierarchy_valid: bool = True
- headings: list[dict[str, str]] = Field(default_factory=list) (level + text)
- image_count: int = 0
- images_with_alt: int = 0
- images_without_alt: int = 0
- internal_link_count: int = 0
- external_link_count: int = 0
- word_count: int = 0
- reading_level: float = 0.0
- is_ssr: bool = True
- has_canonical: bool = False
- canonical_url: Optional[str] = None
- is_noindex: bool = False
- is_nofollow: bool = False
- has_https: bool = True
- has_mixed_content: bool = False
- publish_date: Optional[str] = None
- modified_date: Optional[str] = None
- has_author: bool = False
- author_name: Optional[str] = None
- schema: SchemaDetectionResult = Field(default_factory=SchemaDetectionResult)
- aeo: AEOReadinessResult = Field(default_factory=AEOReadinessResult)
- findings: list[AuditFinding] = Field(default_factory=list)

**AIBotAccessResult** — Site-level bot access:
- gptbot_allowed: bool = True
- claudebot_allowed: bool = True
- perplexitybot_allowed: bool = True
- google_extended_allowed: bool = True
- ccbot_allowed: bool = True
- has_llms_txt: bool = False
- robots_txt_exists: bool = False

**SitemapHealthResult** — Sitemap analysis:
- has_sitemap: bool = False
- sitemap_url_count: int = 0
- sitemap_urls: list[str] = Field(default_factory=list)
- sitemap_errors: list[str] = Field(default_factory=list)
- has_sitemap_index: bool = False

**DimensionScore** — Per-dimension aggregate:
- dimension: AuditDimension = AuditDimension.crawlability
- score: float = 100.0
- weight: float = 0.0
- weighted_score: float = 0.0
- finding_count: int = 0
- critical_count: int = 0
- high_count: int = 0
- medium_count: int = 0
- low_count: int = 0
- info_count: int = 0

**SiteAuditResult** — Complete site-level output:
- audit_id: str = ""
- domain: str = ""
- overall_score: float = 0.0
- grade: str = "F"
- pages_crawled: int = 0
- pages_discovered: int = 0
- duration_seconds: float = 0.0
- dimension_scores: list[DimensionScore] = Field(default_factory=list)
- ai_bot_access: AIBotAccessResult = Field(default_factory=AIBotAccessResult)
- sitemap_health: SitemapHealthResult = Field(default_factory=SitemapHealthResult)
- page_results: list[PageAuditResult] = Field(default_factory=list)
- total_findings: int = 0
- findings_by_severity: dict[str, int] = Field(default_factory=dict)
- findings_by_dimension: dict[str, int] = Field(default_factory=dict)
- top_findings: list[dict[str, Any]] = Field(default_factory=list)
- avg_snippet_readiness: float = 0.0
- pages_with_schema: int = 0
- avg_question_heading_ratio: float = 0.0
- started_at: Optional[datetime] = None
- completed_at: Optional[datetime] = None
- status: str = "pending"
- error_message: Optional[str] = None

## Config (core/site_audit/config.py)

```python
@dataclass(frozen=True)
class AuditConfig:
    dimension_weights: dict[str, float]       # Must sum to 1.0
    grade_thresholds: dict[str, float]        # A >= 90, B >= 75, C >= 60, D >= 40
    severity_penalties: dict[str, float]      # critical=10, high=5, medium=2, low=1, info=0
    title_min_length: int = 30
    title_max_length: int = 60
    meta_min_length: int = 120
    meta_max_length: int = 160
    page_analysis_concurrency: int = 30
    request_timeout: float = 15.0
    max_redirects: int = 5
    aeo_min_question_heading_ratio: float = 0.3
    aeo_ideal_paragraph_word_count_min: int = 20
    aeo_ideal_paragraph_word_count_max: int = 80

DEFAULT_DIMENSION_WEIGHTS = {
    "crawlability": 0.20,
    "performance": 0.10,
    "on_page_seo": 0.15,
    "extractability": 0.20,
    "schema_markup": 0.10,
    "eeat": 0.15,
    "freshness": 0.05,
    "security": 0.05,
}
# Verify: sum = 1.0
```

## Repository (core/db/repositories/site_audit_repo.py)

Extend `SQLAlchemyRepository` from `core/db/repositories/base.py`. Methods: `get_latest_for_company(company_id)`, `list_for_company(company_id, limit)`, `list_for_audit(audit_id)`. Flush-only — never call commit.

## Pipeline Skeleton (core/site_audit/pipeline.py)

```python
async def run_site_audit(input_data: SiteAuditInput, config: AuditConfig = DEFAULT_AUDIT_CONFIG, ...) -> SiteAuditResult:
    raise NotImplementedError("Pipeline steps not yet implemented — will be wired by integrator")
```

## Tests

Test model instantiation with defaults, enum serialization roundtrip, config weight sum validation (assert sum == 1.0), grade threshold ordering, repository flush-only contract, pipeline skeleton raises NotImplementedError.
