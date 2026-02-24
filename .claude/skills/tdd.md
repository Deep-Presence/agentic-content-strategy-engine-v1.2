# Skill: Test-Driven Development (TDD)

> This is a product codebase. Every change ships to production. Tests are not optional.

---

## The TDD Cycle

Every feature, bug fix, or refactor follows Red → Green → Refactor:

```
1. RED    — Write a failing test that defines the desired behavior
2. GREEN  — Write the minimum code to make the test pass
3. REFACTOR — Clean up without changing behavior, re-run tests
```

Never write implementation code without a failing test first. If you catch yourself writing code before the test — stop, delete it, write the test.

---

## Test File Structure

Mirror the `core/` structure under `tests/`:

```
tests/
├── conftest.py                         ← Shared fixtures (API mocks, fixture data loaders)
├── gap_analysis/
│   ├── conftest.py                     ← Gap analysis fixtures
│   ├── test_s1_embed_assets.py
│   ├── test_s2_generate_queries.py
│   ├── test_s3_search_platforms.py
│   ├── test_s4_enrich_citations.py
│   ├── test_s5_embed_content.py
│   ├── test_s6_analyze.py
│   ├── test_s7_visualize.py
│   ├── test_s8_generate_report.py
│   ├── test_pipeline.py                ← Integration: step-to-step data flow
│   └── engines/
│       ├── test_openai_engine.py
│       ├── test_claude_engine.py
│       ├── test_gemini_engine.py
│       └── test_perplexity_engine.py
├── research/
│   ├── test_company_agent.py
│   ├── test_persona_agent.py
│   ├── test_style_guide_agent.py
│   └── test_approval_flow.py
├── models/
│   ├── test_gap_analysis_models.py     ← Serialization roundtrips
│   ├── test_artifact_models.py
│   └── test_persona_models.py
├── reddit_hil/
│   └── test_reddit_graph.py
└── fixtures/                           ← Frozen test data
    ├── ramp/
    │   ├── queries.json
    │   ├── enriched_citations.json
    │   ├── analysis.json
    │   └── company_embeddings.json
    └── sample_html/
        ├── blog_post.html
        ├── pricing_page.html
        └── docs_page.html
```

---

## Test Categories & When to Write Each

### Unit Tests — every function gets one
Test a single function in isolation. Mock all external dependencies.

```python
# Example: testing structural signal extraction
def test_extract_structural_signals_counts_headers():
    """s4 should count headers, not just flag their existence."""
    html = """
    <html><body>
        <h1>Main Title</h1>
        <h2>Section 1</h2>
        <p>Content with a <a href="https://example.com">link</a></p>
        <h2>Section 2</h2>
        <ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>
        <h3>Subsection</h3>
        <p>More content with stat: 45% increase</p>
    </body></html>
    """
    signals = extract_structural_signals(html)
    
    assert signals.header_count == 4          # h1 + 2×h2 + h3
    assert signals.list_item_count == 3       # 3 li elements
    assert signals.paragraph_count == 2       # 2 p elements
    assert signals.stat_count >= 1            # "45%" detected
    assert signals.link_count == 1            # 1 anchor tag
    assert signals.word_count > 0
```

### Contract Tests — every step boundary gets one
Verify that the output of step N is a valid input for step N+1.

```python
# Example: s4 output → s5 input contract
def test_enriched_citation_has_required_fields_for_embedding():
    """s5 expects every EnrichedCitation to have .paragraphs and .url populated."""
    # Load fixture from a real s4 output
    enriched = load_fixture("ramp/enriched_citations.json", EnrichedCitation)
    
    for citation in enriched:
        assert citation.url, f"Citation missing URL: {citation}"
        assert citation.paragraphs is not None, f"Citation missing paragraphs: {citation.url}"
        # s5 skips citations with empty paragraphs, but they should still be a list
        assert isinstance(citation.paragraphs, list)
```

### Serialization Roundtrip Tests — every model gets one
Ensure Pydantic models survive JSON serialization and deserialization, especially with existing artifact data.

```python
# Example: backward compatibility test
def test_analysis_result_roundtrip_with_existing_artifact():
    """Existing analysis.json from Ramp must still deserialize correctly."""
    raw = Path("tests/fixtures/ramp/analysis.json").read_text()
    data = json.loads(raw)
    
    # Must not throw
    result = AnalysisResult(**data)
    
    # Roundtrip
    serialized = json.loads(result.model_dump_json())
    result2 = AnalysisResult(**serialized)
    
    assert result2.proximity_stats == result.proximity_stats
    assert len(result2.gaps) == len(result.gaps)
```

### Regression Tests — every bug fix gets one
When a bug is found and fixed, write a test that would have caught it.

```python
# Example: regression for the zero proximity stats bug
def test_proximity_stats_not_all_zero():
    """Regression: s6 was producing all-zero proximity_stats."""
    queries = load_fixture("ramp/queries_with_embeddings.json", GeneratedQuery)
    company_units = load_fixture("ramp/company_embeddings.json", SemanticUnit)
    enriched = load_fixture("ramp/citations_with_embeddings.json", EnrichedCitation)
    
    analysis = compute_gap_analysis(queries, company_units, enriched)
    
    prox = analysis.proximity_stats
    assert prox.get("citation_similarity_mean", 0) > 0, "citation_similarity_mean is zero"
    assert prox.get("company_similarity_mean", 0) > 0, "company_similarity_mean is zero"
```

### Integration Tests — per pipeline, end-to-end
Test the full pipeline with fixture data and `skip_steps` for speed.

```python
# Example: gap analysis pipeline integration
@pytest.mark.integration
def test_gap_analysis_pipeline_produces_non_empty_report(tmp_path):
    """Full pipeline with fixture data should produce a complete report."""
    input_data = create_test_input(
        company_name="TestCorp",
        company_url="https://example.com",
        platforms=["openai"],  # Single platform for speed
    )
    
    with patch_all_engines():  # Mock all API calls
        report = run_gap_analysis(input_data)
    
    assert report.report_md, "Report markdown is empty"
    assert report.report_json.get("gaps"), "Report has no gaps"
    assert report.generation_spec_json.get("cluster_specs"), "No cluster specs"
```

---

## Mocking Strategy

### LLM API Calls — always mock in unit/contract tests
Never make real API calls in tests. Use `unittest.mock.patch` or `pytest-mock`.

```python
# Shared fixture in conftest.py
@pytest.fixture
def mock_openai_response():
    """Standard mock for OpenAI search engine response."""
    return PlatformResult(
        engine="openai",
        model="gpt-4o",
        query_id="Q1",
        query_text="how does expense management work",
        response_text="Expense management automates the tracking...",
        citations=[
            CitationRef(url="https://example.com/blog/expense", rank=1, source="openai")
        ],
    )

@pytest.fixture
def patch_all_engines(mock_openai_response):
    """Patch all search engines to return mock data."""
    with patch("core.gap_analysis.engines.openai_engine.OpenAIEngine.search", 
               return_value=mock_openai_response):
        yield
```

### HTTP Calls (crawling) — use frozen HTML fixtures

```python
# Fixture HTML files in tests/fixtures/sample_html/
@pytest.fixture
def mock_html_response():
    html = Path("tests/fixtures/sample_html/blog_post.html").read_text()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Mock(status_code=200, text=html, headers={"content-type": "text/html"})
        yield mock_get
```

### Embeddings — use deterministic vectors

```python
@pytest.fixture
def mock_embeddings():
    """Return deterministic embeddings for reproducible similarity tests."""
    def _embed(texts):
        # Deterministic: hash-based pseudo-embeddings
        import hashlib
        vectors = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            vec = [float(b) / 255.0 for b in h] * (3072 // 32)
            vectors.append(vec[:3072])
        return vectors
    
    with patch("core.shared_tools.embedding_client.embed_texts", side_effect=_embed):
        yield
```

---

## Fixture Data Management

### Creating Fixtures from Real Artifacts
Copy from existing production artifacts, then sanitize:

```bash
# One-time setup: create fixture data from Ramp analysis
mkdir -p tests/fixtures/ramp
cp artifacts/gap_analysis/ramp/queries.json tests/fixtures/ramp/
cp artifacts/gap_analysis/ramp/enriched_citations.json tests/fixtures/ramp/
cp artifacts/gap_analysis/ramp/analysis.json tests/fixtures/ramp/
cp artifacts/gap_analysis/ramp/company_embeddings.json tests/fixtures/ramp/
```

### Fixture Loader Helper

```python
# tests/conftest.py
import json
from pathlib import Path
from typing import List, Type, TypeVar

T = TypeVar("T")
FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(relative_path: str, model_cls: Type[T]) -> List[T]:
    """Load a JSON fixture file and deserialize into Pydantic models."""
    data = json.loads((FIXTURES_DIR / relative_path).read_text())
    if isinstance(data, list):
        return [model_cls(**item) for item in data]
    return model_cls(**data)

def load_raw_fixture(relative_path: str) -> dict:
    """Load a JSON fixture as raw dict."""
    return json.loads((FIXTURES_DIR / relative_path).read_text())
```

### Keeping Fixtures Current
When a model changes:
1. Run the pipeline with the new code against real data
2. Copy the new output to fixtures
3. Verify all existing tests still pass with updated fixtures
4. Add a note in the fixture directory: `_fixture_generated.txt` with date and source

---

## Test Naming Convention

```python
def test_{function_name}_{scenario}_{expected_outcome}():
    """Docstring explaining WHAT is being tested and WHY."""
```

Examples:
```python
def test_extract_structural_signals_empty_html_returns_zero_counts():
def test_compute_gap_analysis_with_no_citations_produces_max_gap():
def test_generated_query_model_roundtrip_with_existing_artifact():
def test_enrich_citation_skips_unreachable_urls():
def test_query_gen_prompt_excludes_brand_from_c9_queries():
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific step
pytest tests/gap_analysis/test_s4_enrich_citations.py -v

# By marker
pytest tests/ -m "not integration" -v       # Unit tests only
pytest tests/ -m integration -v              # Integration only

# With coverage
pytest tests/ --cov=core --cov-report=term-missing

# Stop on first failure
pytest tests/ -x -v

# Specific test function
pytest tests/ -k "test_extract_structural_signals" -v
```

---

## pytest Configuration

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: end-to-end pipeline tests (may be slow)",
    "slow: tests that take >10s",
]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["core"]
omit = ["core/config/*", "scripts/*"]
```

---

## Test Priority Order

When adding tests to a codebase with zero coverage, prioritize:

1. **Pydantic model roundtrip tests** — highest bang for buck, catches deserialization regressions
2. **Step boundary contract tests** — ensures data flows correctly between pipeline steps
3. **Core computation tests** — s6 analysis, similarity calculations, SPA scoring
4. **Structural extraction tests** — s4 HTML parsing, signal counting
5. **Report generation tests** — s8 template rendering with computed data
6. **Query generation tests** — s2 prompt output validation
7. **Engine response parsing tests** — citation extraction from each provider
8. **Integration tests** — full pipeline with mocked APIs
9. **Research pipeline tests** — LangGraph approval flow branches

---

## Common Pitfalls in This Codebase

### Async testing
Many pipeline functions use `asyncio.run()` or `asyncio.to_thread()`. Use `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_search_platforms_returns_results():
    with patch_all_engines():
        results = await search_platforms(queries, platforms=["openai"])
    assert len(results) > 0
```

### Pydantic v2 gotchas
- Use `model_dump(mode="json")` not `model_dump()` when testing serialization (mode="json" converts enums to strings, datetimes to ISO strings)
- Test with `model_validate(data)` not just `Model(**data)` — validate catches more issues

### Large fixture files
If fixture JSONs are too large for git (>1MB), add them to `.gitignore` and document how to regenerate them in `tests/fixtures/README.md`.

### Embedding dimension
Tests that create mock embeddings must use the correct dimension (3072 for text-embedding-3-large). A wrong dimension will cause silent cosine similarity errors.