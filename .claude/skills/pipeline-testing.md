# Skill: Pipeline Testing

> How to write tests for the content-strategy-engine's 8-step gap analysis pipeline.

---

## Engine Mocking — Per Provider

Every engine inherits from `core.gap_analysis.engines.base.SearchEngine` and exposes an `async search(query_text, query_id) -> PlatformResult` method. Each provider has different SDK patterns that need different mocking.

### OpenAI Engine (`core.gap_analysis.engines.openai_engine`)

The OpenAI engine uses `client.responses.create()` (experimental responses API) inside `asyncio.to_thread()`. Mock at the SDK level:

```python
import pytest
from unittest.mock import patch, MagicMock
from core.gap_analysis.engines.openai_engine import OpenAIEngine
from core.models.gap_analysis import PlatformResult, CitationRef


@pytest.fixture
def mock_openai_sdk():
    """Mock OpenAI responses.create() with url_citation annotations."""
    mock_response = MagicMock()
    # Build the nested output structure OpenAI returns
    annotation = MagicMock()
    annotation.type = "url_citation"
    annotation.url = "https://example.com/cited-article"

    text_part = MagicMock()
    text_part.type = "output_text"
    text_part.text = "Expense management software automates tracking and approval of business spending."
    text_part.annotations = [annotation]

    message = MagicMock()
    message.type = "message"
    message.content = [text_part]

    mock_response.output = [message]

    with patch("core.gap_analysis.engines.openai_engine.OpenAI") as MockClient:
        MockClient.return_value.responses.create.return_value = mock_response
        yield MockClient


@pytest.mark.asyncio
async def test_openai_engine_extracts_citations(mock_openai_sdk):
    engine = OpenAIEngine(model="gpt-4o-test")
    result = await engine.search("how does expense management work", "Q1")

    assert result.engine == "openai"
    assert result.query_id == "Q1"
    assert len(result.citations) == 1
    assert str(result.citations[0].url) == "https://example.com/cited-article"
    assert "expense management" in result.response_text.lower()
```

### Claude Engine (`core.gap_analysis.engines.claude`)

Claude uses `client.messages.create()` with `tools=[{"type": "web_search"}]`. Citation URLs are in `block.citations[].url`:

```python
@pytest.fixture
def mock_claude_sdk():
    """Mock Anthropic messages.create() with web_search citations."""
    citation = MagicMock()
    citation.url = "https://example.com/claude-cited"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Cap table management platforms help companies track equity ownership."
    text_block.citations = [citation]

    mock_response = MagicMock()
    mock_response.content = [text_block]

    with patch("core.gap_analysis.engines.claude.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response
        yield mock_anthropic


@pytest.mark.asyncio
async def test_claude_engine_extracts_citations(mock_claude_sdk):
    engine = ClaudeEngine(model="claude-test")
    result = await engine.search("what is cap table management", "Q2")

    assert result.engine == "claude"
    assert len(result.citations) >= 1
    assert "example.com" in str(result.citations[0].url)
```

### Gemini Engine (`core.gap_analysis.engines.gemini`)

Gemini uses `client.models.generate_content()` with `google_search` tool. Citations are in `grounding_metadata.grounding_chunks[].web.uri`:

```python
@pytest.fixture
def mock_gemini_sdk():
    """Mock Google GenAI with grounding_metadata chunks."""
    chunk = MagicMock()
    chunk.url = None
    chunk.web = MagicMock()
    chunk.web.uri = "https://example.com/gemini-cited"

    grounding = MagicMock()
    grounding.grounding_chunks = [chunk]

    mock_response = MagicMock()
    mock_response.text = "Integration platforms connect enterprise systems for seamless data flow."
    mock_response.grounding_metadata = grounding

    with patch("core.gap_analysis.engines.gemini.genai") as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response
        yield mock_genai


@pytest.mark.asyncio
async def test_gemini_engine_extracts_citations(mock_gemini_sdk):
    engine = GeminiEngine(model="gemini-test")
    result = await engine.search("enterprise integration platforms", "Q3")

    assert result.engine == "gemini"
    assert len(result.citations) >= 1
    # Gemini often returns vertexaisearch redirects — test the raw URL
    assert "example.com" in str(result.citations[0].url)
```

### Perplexity Engine (`core.gap_analysis.engines.perplexity`)

Perplexity uses `client.chat.completions.create()`. Citations are a top-level list on the completion object:

```python
@pytest.fixture
def mock_perplexity_sdk():
    """Mock Perplexity chat completions with top-level citations list."""
    msg = MagicMock()
    msg.content = "The best spend management tools for enterprises include automated workflows."

    choice = MagicMock()
    choice.message = msg

    mock_completion = MagicMock()
    mock_completion.choices = [choice]
    mock_completion.citations = [
        "https://example.com/perplexity-cited-1",
        "https://example.com/perplexity-cited-2",
    ]

    with patch("core.gap_analysis.engines.perplexity.Perplexity") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = mock_completion
        yield MockClient


@pytest.mark.asyncio
async def test_perplexity_engine_extracts_multiple_citations(mock_perplexity_sdk):
    engine = PerplexityEngine(model="sonar-test")
    result = await engine.search("best spend management tools", "Q4")

    assert result.engine == "perplexity"
    assert len(result.citations) == 2
    assert result.citations[0].rank == 1
    assert result.citations[1].rank == 2
```

### Combined Engine Patch (for integration tests)

```python
@pytest.fixture
def patch_all_engines():
    """Patch all 4 engines to return deterministic mock results."""
    async def mock_search(self, query_text, query_id=None):
        return PlatformResult(
            engine=self.engine_name,
            model=self.model,
            query_id=query_id or "",
            query_text=query_text,
            response_text=f"Mock response from {self.engine_name} for: {query_text}",
            citations=[
                CitationRef(
                    url=f"https://example.com/{self.engine_name}-cited",
                    rank=1,
                    source=self.engine_name,
                )
            ],
        )

    with patch.object(OpenAIEngine, "search", mock_search), \
         patch.object(ClaudeEngine, "search", mock_search), \
         patch.object(GeminiEngine, "search", mock_search), \
         patch.object(PerplexityEngine, "search", mock_search):
        yield
```

---

## Fixture Data from Real Artifacts

### One-Time Setup

Copy sanitized data from production runs. These become your ground truth for regression tests:

```bash
# Create fixture directory
mkdir -p tests/fixtures/ramp tests/fixtures/sample_html

# Copy from existing Ramp analysis (the most complete dataset)
cp artifacts/gap_analysis/ramp/queries.json tests/fixtures/ramp/
cp artifacts/gap_analysis/ramp/enriched_citations.json tests/fixtures/ramp/
cp artifacts/gap_analysis/ramp/analysis.json tests/fixtures/ramp/
cp artifacts/gap_analysis/ramp/company_embeddings.json tests/fixtures/ramp/

# Copy embedding files if they exist
cp artifacts/gap_analysis/ramp/embeddings/queries_with_embeddings.json tests/fixtures/ramp/ 2>/dev/null
cp artifacts/gap_analysis/ramp/embeddings/citations_with_embeddings.json tests/fixtures/ramp/ 2>/dev/null
```

### Fixture Size Warning

Embedding JSONs can be huge (100MB+ with 3072-dim vectors × hundreds of items). For unit tests, create **slim fixtures** — take the first 5-10 items:

```python
# scripts/create_slim_fixtures.py
import json
from pathlib import Path

FIXTURES = Path("tests/fixtures/ramp")
for name in ["queries.json", "enriched_citations.json", "company_embeddings.json"]:
    full = json.loads((FIXTURES / name).read_text())
    slim = full[:10] if isinstance(full, list) else full
    (FIXTURES / f"slim_{name}").write_text(json.dumps(slim, indent=2))
```

### Fixture Loader (put in `tests/conftest.py`)

```python
import json
from pathlib import Path
from typing import List, Type, TypeVar, Union

T = TypeVar("T")
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(relative_path: str, model_cls: Type[T]) -> Union[T, List[T]]:
    """Load JSON fixture and deserialize into Pydantic model(s)."""
    data = json.loads((FIXTURES_DIR / relative_path).read_text())
    if isinstance(data, list):
        return [model_cls(**item) for item in data]
    return model_cls(**data)


def load_raw_fixture(relative_path: str) -> Union[dict, list]:
    """Load JSON fixture as raw dict/list."""
    return json.loads((FIXTURES_DIR / relative_path).read_text())


def sample_html(name: str) -> str:
    """Load a sample HTML file for s4 enrichment testing."""
    return (FIXTURES_DIR / "sample_html" / name).read_text()
```

### Sample HTML Fixtures

Create realistic HTML files for testing `s4_enrich_citations.py` — the `_extract_paragraphs()` function:

**`tests/fixtures/sample_html/blog_post.html`** — a typical B2B blog post with headers, lists, stats:
```html
<html><body>
<h1>How Expense Management Software Saves Enterprise Teams 40% of Processing Time</h1>
<p>Managing business expenses manually leads to errors, delays, and frustrated employees. Modern expense management platforms automate the entire workflow from receipt capture to reimbursement.</p>
<h2>Key Benefits of Automated Expense Management</h2>
<p>According to a 2024 Gartner report, companies using automated expense tools see a 40% reduction in processing time and 25% fewer policy violations compared to manual processes.</p>
<ul>
  <li>Automated receipt scanning and data extraction using OCR</li>
  <li>Real-time policy enforcement at the point of spend</li>
  <li>Integration with accounting systems like NetSuite and QuickBooks</li>
  <li>Mobile-first employee experience for on-the-go submissions</li>
</ul>
<h2>Implementation Best Practices</h2>
<p>Start with a pilot group of 50-100 employees before rolling out company-wide. Set clear expense categories and approval chains. Integrate with your existing ERP within the first 30 days.</p>
<h3>Common Pitfalls</h3>
<p>The most frequent implementation mistake is not training managers on the approval workflow. Without proper training, approval bottlenecks negate the automation benefits.</p>
</body></html>
```

**`tests/fixtures/sample_html/thin_page.html`** — a JS-rendered page with minimal content:
```html
<html><body>
<div id="root"></div>
<script src="/bundle.js"></script>
<noscript>Enable JavaScript to view this page.</noscript>
</body></html>
```

---

## Step Boundary Contract Tests

These verify the output of step N is valid input for step N+1.

### s1 → s2 Contract
s2 doesn't directly consume s1 output (it uses input_data), but s1 writes `company_embeddings.json` used by s6:

```python
def test_s1_output_valid_for_s6():
    """company_embeddings.json must contain SemanticUnits with embeddings."""
    units = load_fixture("ramp/company_embeddings.json", SemanticUnit)
    assert len(units) > 0, "No company units produced"

    for unit in units[:5]:  # Spot check first 5
        assert unit.text, f"SemanticUnit {unit.unit_id} has empty text"
        assert unit.unit_id, "SemanticUnit missing unit_id"
        # Embeddings may be None if s5 hasn't run yet — that's OK for s1 output
```

### s2 → s3 Contract
```python
def test_s2_output_valid_for_s3():
    """queries.json must have query_id, query_text, and cluster_name for s3."""
    queries = load_fixture("ramp/queries.json", GeneratedQuery)
    assert len(queries) > 0

    for q in queries:
        assert q.query_id, f"Query missing query_id: {q}"
        assert q.query_text, f"Query {q.query_id} has empty query_text"
        assert q.cluster_name, f"Query {q.query_id} has no cluster_name"
        assert q.cluster_id, f"Query {q.query_id} has no cluster_id"
```

### s3 → s4 Contract
```python
def test_s3_output_valid_for_s4():
    """PlatformResult must have citations with parseable URLs."""
    # s3 output is JSONL per engine — load from fixture
    result = PlatformResult(
        engine="openai",
        model="gpt-4o",
        query_id="Q1",
        query_text="test query",
        response_text="test response",
        citations=[CitationRef(url="https://example.com/article", rank=1, source="openai")],
    )
    # s4 expects: result.citations[].url to be a valid URL string
    for citation in result.citations:
        url_str = str(citation.url)
        assert url_str.startswith("http"), f"Citation URL not HTTP: {url_str}"
```

### s4 → s5 Contract (CRITICAL — this is where data often breaks)
```python
def test_s4_output_valid_for_s5():
    """EnrichedCitation must have paragraphs list and structural_signals for s5 embedding."""
    enriched = load_fixture("ramp/enriched_citations.json", EnrichedCitation)
    assert len(enriched) > 0

    for ec in enriched[:10]:
        assert isinstance(ec.paragraphs, list), f"paragraphs not a list for {ec.url}"
        assert ec.url, "EnrichedCitation missing URL"
        # s5 embeds paragraphs — empty is OK (skipped) but must be a list
        if ec.structural_signals:
            assert ec.structural_signals.word_count >= 0
```

### s5 → s6 Contract
```python
def test_s5_output_valid_for_s6():
    """After s5, queries and citations must have embeddings for similarity computation."""
    queries = load_fixture("ramp/slim_queries_with_embeddings.json", GeneratedQuery)

    has_embedding = sum(1 for q in queries if q.embedding)
    assert has_embedding > 0, "No queries have embeddings after s5"

    for q in queries:
        if q.embedding:
            assert len(q.embedding) == 3072, f"Wrong embedding dimension: {len(q.embedding)}"
```

### s6 → s8 Contract
```python
def test_s6_output_valid_for_s8():
    """AnalysisResult must have populated fields for report generation."""
    analysis = load_fixture("ramp/analysis.json", AnalysisResult)

    assert analysis.gaps, "No gaps in analysis — s8 needs gaps for report"
    assert analysis.proximity_stats, "Empty proximity_stats"
    assert analysis.cluster_specs is not None, "cluster_specs is None"

    for gap in analysis.gaps[:5]:
        assert gap.query_id, "Gap missing query_id"
        assert gap.query_text, "Gap missing query_text"
        assert gap.gap is not None, f"Gap score is None for {gap.query_id}"
```

---

## Pydantic Model Roundtrip Tests

Every model that gets serialized to JSON and loaded back must survive the roundtrip:

```python
import json
import pytest
from core.models.gap_analysis import (
    AnalysisResult, EnrichedCitation, GeneratedQuery,
    GapAnalysisInput, PlatformResult, SemanticUnit,
    StructuralSignals, QueryGap, ClusterContentSpec,
)


@pytest.mark.parametrize("fixture_path,model_cls", [
    ("ramp/queries.json", GeneratedQuery),
    ("ramp/enriched_citations.json", EnrichedCitation),
    ("ramp/company_embeddings.json", SemanticUnit),
])
def test_list_model_roundtrip(fixture_path, model_cls):
    """JSON list fixtures must roundtrip through Pydantic without data loss."""
    raw = json.loads((FIXTURES_DIR / fixture_path).read_text())
    models = [model_cls(**item) for item in raw]

    for original_data, model in zip(raw, models):
        reserialized = json.loads(model.model_dump_json())
        model_back = model_cls(**reserialized)
        # Key fields must survive
        for key in original_data:
            if key == "embedding":
                continue  # Skip large vectors for speed
            assert getattr(model_back, key, None) is not None or original_data[key] is None


def test_analysis_result_roundtrip():
    """The big one — AnalysisResult contains nested models."""
    raw = load_raw_fixture("ramp/analysis.json")
    result = AnalysisResult(**raw)

    serialized = json.loads(result.model_dump_json())
    result2 = AnalysisResult(**serialized)

    assert len(result2.gaps) == len(result.gaps)
    assert len(result2.spa_results) == len(result.spa_results)
    assert len(result2.cluster_specs) == len(result.cluster_specs)
    assert result2.proximity_stats == result.proximity_stats
```

---

## HTTP Mocking for s4 Enrichment

s4 uses `httpx.Client.get()` to crawl URLs. Mock it with frozen HTML:

```python
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_httpx_get():
    """Return fixture HTML for any URL."""
    html = sample_html("blog_post.html")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_response.headers = {"content-type": "text/html"}

    with patch("core.gap_analysis.steps.s4_enrich_citations.httpx.Client") as MockClient:
        MockClient.return_value.__enter__ = MagicMock(return_value=MockClient.return_value)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)
        MockClient.return_value.get.return_value = mock_response
        yield MockClient
```

---

## Embedding Mocking

s5 calls `core.shared_tools.embedding_client.embed_texts()`. For tests, use deterministic hash-based vectors:

```python
import hashlib

@pytest.fixture
def mock_embed_texts():
    """Deterministic pseudo-embeddings for reproducible similarity tests."""
    def _embed(texts: list[str]) -> list[list[float]]:
        vectors = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            vec = [float(b) / 255.0 for b in h] * (3072 // 32)
            vectors.append(vec[:3072])
        return vectors

    with patch("core.shared_tools.embedding_client.embed_texts", side_effect=_embed):
        yield

    # IMPORTANT: These vectors have consistent similarity properties:
    # - Same text → identical vector → cosine sim = 1.0
    # - Different text → different vector → cosine sim ~ 0.3-0.7
    # This makes similarity threshold tests reproducible.
```
