# Core Shared Tools

> **Location:** `core/shared_tools/`
> **Owner:** Core
> **Dependencies:** OpenAI SDK, LangSmith, structlog, pgvector, boto3 (indirect)
> **Dependents:** All pipelines (embeddings, tracing, logging, cost tracking)
> **Last Updated:** 2026-04-09

## Overview

The shared tools module contains cross-cutting utilities used by all pipelines: embedding clients (async + sync), vector storage (pgvector), LLM cost tracking, LangSmith tracing, structured logging configuration, task status enum, text extraction, knowledge document metadata I/O, and OpenRouter client management. These are the foundational building blocks that every pipeline depends on.

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Package marker | (empty) |
| `async_embedding_client.py` | Async OpenAI embeddings via OpenRouter | `async_embed_texts` |
| `embedding_client.py` | Sync OpenAI embeddings via OpenRouter | `embed_texts` |
| `vector_store.py` | pgvector-backed vector storage | `VectorStoreClient`, convenience functions |
| `cost_tracker.py` | LLM cost tracking + DB persistence | `track_llm_cost`, `estimate_cost`, usage extractors |
| `tracing.py` | LangSmith tracing integration | `create_pipeline_trace`, `create_span`, `log_generation` |
| `structured_logging.py` | structlog configuration | `configure_logging`, `bind_context`, `scoped_bind` |
| `openrouter_client.py` | OpenRouter client factory | `get_async_client`, `get_sync_client`, `_ensure_model_prefix` |
| `task_status.py` | Shared TaskStatus enum | `TaskStatus` |
| `text_extraction.py` | Document text extraction | `extract_text`, `extract_text_from_bytes` |
| `knowledge_doc_metadata.py` | Knowledge doc metadata I/O | `load_metadata`, `save_metadata`, `mark_documents_embedded` |
| `math_utils.py` | Mathematical utilities | `cosine_similarity` |

## Detailed Reference

### Embedding Clients

#### `async_embedding_client.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `async_embed_texts` | `(texts: List[str], batch_size=None, max_concurrent_batches=None) -> List[List[float]]` | Main entry. Chunks long texts, embeds via AsyncOpenAI, mean-pools chunks |
| `_chunk_text` | `(text: str, max_chars=26211) -> List[str]` | Splits text at conservative 3.2 chars/token limit |
| `_average_embeddings` | `(embeddings: List[List[float]]) -> List[float]` | Mean-pool + L2-normalize |
| `_retry_async` | `(fn, max_retries=3, base_delay=1.0) -> T` | Jittered exponential backoff |

#### `embedding_client.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `embed_texts` | `(texts: List[str], batch_size=64) -> List[List[float]]` | Sync variant. Batches, retries, tracks cost |

Both clients route through OpenRouter with automatic cost tracking via `track_llm_cost()`.

### `vector_store.py` — pgvector Backend

`VectorStoreClient` replaces the old ChromaDB client. Per-function session isolation.

| Method | Description |
|--------|-------------|
| `upsert_embeddings(company_slug, unit_ids, texts, embeddings, metadatas)` | Upsert semantic unit embeddings (S1). Batch size 500 |
| `get_embeddings_by_ids(company_slug, unit_ids)` | Get specific embeddings |
| `get_all_embeddings(company_slug)` | Get all embeddings for company |
| `collection_exists(company_slug)` | Check if any embeddings exist |
| `delete_company_embeddings(company_slug)` | Delete all for company |
| `upsert_citation_embeddings(company_slug, embedding_ids, documents, embeddings)` | Upsert citation paragraph embeddings (S5). ON CONFLICT DO UPDATE |
| `upsert_persona_embeddings(effective_slug, persona_ids, texts, embeddings)` | Upsert persona embeddings |
| `get_persona_embeddings(effective_slug, persona_ids=None)` | Get persona embeddings |

Module-level convenience functions (drop-in for old async_chroma_client): `async_upsert_embeddings`, `async_get_all_embeddings`, `async_get_embeddings_by_ids`, `async_delete_company_collection`, `async_collection_exists`, `async_upsert_citation_embeddings`, `async_upsert_persona_embeddings`, `async_get_persona_embeddings`.

### `cost_tracker.py` — LLM Cost Tracking

| Function | Signature | Description |
|----------|-----------|-------------|
| `track_llm_cost` | `(*, model, provider, pipeline, pipeline_step, prompt_tokens, completion_tokens, company_slug="", ...) -> None` | Structured log + fire-and-forget DB write. **Never raises** |
| `estimate_cost` | `(*, model, provider, prompt_tokens, completion_tokens) -> float` | Returns USD estimate |
| `_match_price` | `(model: str) -> tuple[float, float]` | Fuzzy model→pricing lookup |

**Usage extractors** (one per provider format):
- `extract_usage_anthropic_http(data)` / `extract_usage_anthropic_sdk(response)`
- `extract_usage_gemini_http(data)`
- `extract_usage_openai_responses(response)`
- `extract_usage_litellm(response)`
- `extract_usage_langchain_openai(response)`

**Pricing table** (per 1M tokens):

| Model | Input | Output |
|-------|-------|--------|
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-opus-4-6 | $15.00 | $75.00 |
| claude-haiku-4-5 | $0.80 | $4.00 |
| gpt-5.2 | $2.00 | $8.00 |
| sonar-pro | $3.00 | $15.00 |
| sonar-deep-research | $2.00 | $8.00 |
| gemini-3-flash-preview | $0.10 | $0.40 |
| text-embedding-3-small | $0.02 | $0.00 |

### `tracing.py` — LangSmith Integration

Unified tracing module. Backward-compatible with old Langfuse kwargs.

| Function | Signature | Description |
|----------|-----------|-------------|
| `create_pipeline_trace` | `(session_id, company_slug, ...) -> Optional[RunTree]` | Top-level pipeline trace |
| `create_trace` | `(session_id, name, ...) -> Optional[RunTree]` | Standalone trace |
| `create_span` | `(parent, name, ...) -> Optional[RunTree]` | Child span |
| `end_span` | `(span, output=None, error=None, ...) -> None` | End span with output/error |
| `log_generation` | `(parent, name, model, input_text, output_text, ...) -> None` | Log LLM call with cost metadata |
| `log_score` | `(parent, name, value, comment="", ...) -> None` | Log metric/score |
| `update_trace_output` | `(trace, output=None, ...) -> None` | Finalize trace |
| `create_research_trace` | `(slug, company_name="", ...) -> Optional[RunTree]` | KB pipeline trace |

Context-var span propagation (`_current_span: ContextVar`) for sync LangGraph nodes.

### `structured_logging.py` — Logging Configuration

| Function | Signature | Description |
|----------|-----------|-------------|
| `configure_logging` | `(*, level="INFO", log_format="console", include_caller=False, ...) -> None` | One-time setup for structlog + stdlib bridge |
| `bind_context` | `(**kwargs) -> None` | Bind context vars (request/task scope) |
| `clear_context` | `() -> None` | Clear all context vars |
| `get_context` | `() -> dict` | Get current context (testing) |
| `scoped_bind` | `(**kwargs) -> Iterator[None]` | Context manager for temporary bindings |

Features: sensitive data masking (Layer 7), ISO timestamps, JSON/console renderers, suppresses noisy third-party loggers.

### `openrouter_client.py` — Client Factory

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_async_client` | `() -> AsyncOpenAI` | Cached async client. Raises if no API key |
| `get_sync_client` | `(timeout_s=300.0) -> OpenAI` | Cached sync client |
| `_ensure_model_prefix` | `(model: str) -> str` | Auto-prefix: claude-*→anthropic/, sonar→perplexity/, gpt-*→openai/, gemini-*→google/ |
| `build_chat_openai_via_openrouter` | `(model: str, **kwargs) -> ChatOpenAI` | LangChain ChatOpenAI via OpenRouter |
| `reset_clients` | `() -> None` | Reset singletons (testing) |

### `task_status.py`

```python
class TaskStatus(str, Enum):
    RUNNING = "running"
    PENDING_APPROVAL = "pending_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    FAILED_RESTART = "failed_restart"
```

Shared between `core/` and `api/` (moved here to resolve architecture violation).

### `text_extraction.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `extract_text` | `(file_path: Path) -> str` | Extract text from .md, .txt, .pdf, .docx |
| `extract_text_from_bytes` | `(content: bytes, suffix: str) -> str` | Same but from in-memory bytes (R2 migration) |

### `knowledge_doc_metadata.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `load_metadata` | `(effective_slug, *, storage) -> List[KnowledgeDocument]` | Load from StorageBackend |
| `save_metadata` | `(effective_slug, docs, *, storage) -> None` | Atomic write to StorageBackend |
| `mark_documents_embedded` | `(effective_slug, *, storage) -> int` | Thread-safe mark-as-embedded |
| `doc_storage_key` | `(effective_slug, stored_filename) -> str` | Build storage key |

Uses process-wide `threading.Lock` for metadata write coordination.

### `math_utils.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `cosine_similarity` | `(a: List[float], b: List[float]) -> float` | Cosine similarity. Returns 0.0 if zero magnitude |
