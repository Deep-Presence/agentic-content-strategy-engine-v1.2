# Site Audit — API + Service Layer Specification

## Study These Files FIRST (exact patterns to follow)

```
api/routers/gap_analysis.py               # POST /start pattern: tenant isolation, force_rerun, slug lock
api/routers/gap_data.py                   # Data retrieval: company-scoped endpoints
core/services/gap_data.py                 # @runtime_checkable Protocol definition
core/services/json_gap_data.py            # Filesystem-backed implementation with asyncio.to_thread()
api/dependencies.py                       # DI wiring: get_*_service() functions
api/tasks/runner.py                       # Background task: run_gap_pipeline_task()
api/schemas/gap_data.py                   # Response models with all-default fields
api/schemas/common.py                     # PipelineRunResponse (reuse this, don't duplicate)
api/auth/dependencies.py                  # require_auth, require_role, require_tenant
tests/api/test_gap_analysis.py            # Test patterns: AuthTestClient fixtures
tests/api/conftest.py                     # Shared test fixtures
```

## API Schemas (api/schemas/site_audit.py)

**SiteAuditStartRequest(BaseModel):** company_name (str), domain (str), product_slug (Optional[str] = None), max_pages (int = Field(default=200, ge=1, le=2000)), max_depth (int = Field(default=4, ge=1, le=10)), check_core_web_vitals (bool = True), check_schema_validation (bool = True), check_ai_bot_access (bool = True), force_rerun (bool = False).

**AuditSummaryResponse, AuditDetailResponse, AuditFindingsResponse, AuditPageResultsResponse** — All fields must have defaults. Follow the exact pattern from api/schemas/gap_data.py.

## Router (api/routers/site_audit.py)

```python
router = APIRouter(prefix="/api/v1/site-audit", tags=["site-audit"])
```

### 6 Endpoints

**POST /start** — Start audit pipeline. Auth: `require_role("member", "superuser")`. Must include: (1) tenant isolation check, (2) force_rerun guard checking artifacts directory existence, (3) slug lock via task_store to prevent concurrent runs, (4) `asyncio.create_task()` for background execution, (5) return 202 with `PipelineRunResponse` from `api/schemas/common.py`.

**GET /status/{run_id}** — Poll run status. Auth: `require_auth`. Read from task_store.

**GET /companies/{slug}/audits** — List audits for company. Auth: `require_tenant`. Query param: `limit` (default 20).

**GET /companies/{slug}/audits/{audit_id}** — Full audit detail. Auth: `require_tenant`.

**GET /companies/{slug}/audits/{audit_id}/findings** — Paginated findings. Auth: `require_tenant`. Query params: severity (optional filter), dimension (optional filter), page (default 1), page_size (default 50).

**GET /companies/{slug}/audits/{audit_id}/pages** — Per-page results. Auth: `require_tenant`. Query params: page (default 1), page_size (default 50).

## Service Protocol (core/services/site_audit_data.py)

```python
@runtime_checkable
class SiteAuditDataServiceProtocol(Protocol):
    async def get_audit_summary(self, company_slug: str, audit_id: str) -> dict: ...
    async def get_audit_detail(self, company_slug: str, audit_id: str) -> dict: ...
    async def list_audits(self, company_slug: str, limit: int = 20) -> list[dict]: ...
    async def get_findings(self, company_slug: str, audit_id: str, severity: str | None = None, dimension: str | None = None, page: int = 1, page_size: int = 50) -> dict: ...
    async def get_page_results(self, company_slug: str, audit_id: str, page: int = 1, page_size: int = 50) -> dict: ...
    async def audit_exists(self, company_slug: str, domain: str) -> bool: ...
    async def get_latest_audit_id(self, company_slug: str, domain: str) -> str | None: ...
```

## JSON Service (core/services/json_site_audit_data.py)

Reads from `artifacts/site_audit/{company_slug}/{audit_id}/audit_result.json`. Pattern: module-level FIFO cache (10 entries), slug validation via regex + HTTPException(400), graceful degradation for missing artifacts, sync functions wrapped in `asyncio.to_thread()`.

## DI Wiring (APPEND to api/dependencies.py)

```python
def get_site_audit_data_service(request: Request) -> SiteAuditDataServiceProtocol:
    service = getattr(request.app.state, "site_audit_data_service", None)
    if service is not None:
        return service
    return JsonSiteAuditDataService(artifacts_root=request.app.state.artifacts_root)
```

## Runner (APPEND to api/tasks/runner.py)

`run_site_audit_task()` follows `run_gap_pipeline_task()` exactly: derive slugs → acquire semaphore → emit pipeline_start → call run_site_audit() → save artifacts → update task_store → emit pipeline_complete. Catch ALL exceptions (including ImportError for unwired pipeline), update task_store to failed, emit error event. Never let exceptions propagate.

## CLI (scripts/run_site_audit.py)

Argparse script: `--domain`, `--company`, `--max-pages`, `--max-depth`. Constructs SiteAuditInput, calls `asyncio.run(run_site_audit(input))`, prints progress. Follow `scripts/run_gap_analysis.py` pattern.

## App Registration (APPEND to api/app.py)

```python
from api.routers import site_audit as site_audit_router
app.include_router(site_audit_router.router)
```

## Tests (tests/api/test_site_audit.py — 25+ tests)

Use AuthTestClient from conftest. Create mock audit artifacts in tmp_path for service tests.

**TestStartSiteAudit:** happy path 202, requires auth 401, requires member role 403, tenant isolation 403, already_exists guard 200, force_rerun bypasses guard, slug lock conflict 409, validates domain 422.

**TestListAudits:** returns audits, empty company, requires tenant.

**TestGetAuditDetail:** returns full result, not found 404, requires tenant.

**TestGetFindings:** paginated, filter by severity, filter by dimension.

**TestGetPageResults:** paginated, not found.
