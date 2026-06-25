# Testing Guide

> **Location:** `tests/`
> **Owner:** Full Stack
> **Dependencies:** pytest, pytest-asyncio, httpx (AsyncClient)
> **Last Updated:** 2026-04-09

## Overview

~2,100+ tests organized by domain across 299 test files. Tests mirror `core/` and `api/` structure. All LangGraph checkpoints are patched to `MemorySaver` (no Redis in CI). All LLM calls are mocked — zero real API calls in tests.

## Test Organization

| Directory | Files | Coverage |
|-----------|-------|----------|
| `tests/api/` | 55 | API routers, auth, schemas |
| `tests/content_engine/` | 34 | Content generation pipeline |
| `tests/services/` | 28 | Service layer (Json + Db) |
| `tests/db/` | 23 | ORM models, repositories |
| `tests/topic_discovery/` | 17 | Topic discovery pipeline |
| `tests/daily_tracker/` | 13 | Daily tracking |
| `tests/shared_tools/` | 11 | Embeddings, tracing, cost |
| `tests/integration/` | 9 | End-to-end flows |
| `tests/cms/` | 6 | CMS integration |
| `tests/gap_analysis/` | 6 | Gap analysis steps |
| `tests/analytics/` | 5 | GA4 integration |
| `tests/storage/` | 4 | Storage backends |
| `tests/audit/` | 4 | Audit logging |
| `tests/research/` | 3 | Research pipelines |
| `tests/onboarding/` | 3 | Onboarding flow |
| Others | ~78 | Config, models, events, etc. |

## Key Fixtures (`conftest.py`)

### Root conftest

```python
@pytest.fixture(autouse=True)
def _use_memory_checkpointer(monkeypatch):
    """Patches all 5 LangGraph modules to use MemorySaver instead of Redis."""
    # Patched: graph_v13, audience_persona.graph, knowledge_base.graph,
    #          voice_style_guide.graph, topic_discovery.graph
```

```python
@pytest.fixture
def mock_openai_embeddings(monkeypatch):
    """Deterministic 8-dim fake embeddings based on text length."""
```

```python
@pytest.fixture
def mock_settings(monkeypatch):
    """Test API keys and model configuration without real credentials."""
```

### API conftest (`tests/api/conftest.py`)

```python
@pytest.fixture
def client(app) -> TestClient:
    """Authenticated test client (member role)."""

@pytest.fixture
def public_client(app) -> TestClient:
    """Unauthenticated test client."""

@pytest.fixture
def viewer_client(app) -> TestClient:
    """Viewer-role authenticated client."""
```

Uses `InMemoryEventBus` and mocked `DbTaskStore`.

## Test Patterns

### API Tests
```python
def test_gap_summary_returns_200(client):
    response = client.get("/api/v1/gap-data/summary?slug=test-co")
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
```

### Pipeline Tests
```python
@pytest.mark.asyncio
async def test_site_audit_completes(mock_settings, tmp_path):
    input_data = SiteAuditInput(company_name="Test Co", domain="example.com")
    result = await run_site_audit(input_data, output_dir=tmp_path)
    assert result.status == "completed"
    assert result.overall_score >= 0
```

### Service Tests
```python
@pytest.mark.asyncio
async def test_json_gap_data_get_summary(tmp_path):
    svc = JsonGapDataService(storage=LocalStorageBackend(tmp_path), ...)
    result = await svc.get_summary("test-co")
    assert result is not None
```

## Key Rules

1. **Mock all LLM calls** — never make real HTTP/API calls
2. **Pipeline payloads** use `company_name: "Test Co"` (slug: `"test-co"`)
3. **Monkeypatch `get_sync_redis_or_none` → `None`** in autouse fixtures (disables Redis cache)
4. **Each `tests/db/` file** needs own `pytestmark` auto-skip (conftest pytestmark doesn't propagate)
5. **Patch `asyncio.create_task`** at module level for DbTaskStore tests
6. **TDD mandatory** — write test FIRST, then implementation

## Running Tests

```bash
# Full suite
pytest tests/ -v

# Specific module
pytest tests/content_engine/ -v

# Specific test
pytest tests/ -k "test_name" -v

# With coverage
pytest tests/ --cov=core --cov-report=term-missing
```
