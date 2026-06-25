from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOTS = ("api", "core")

PLATFORM_KEY_ATTRS = {
    "anthropic_api_key",
    "google_api_key_gap_analysis",
    "openai_api_key",
    "openrouter_api_key",
    "perplexity_api_key",
}

SINGLETON_CLIENT_CALLS = {
    "build_chat_openai_via_openrouter",
    "get_async_client",
    "get_sync_client",
}

# Shrink-only BYOK transition allowlist. Customer launch routes preflight and pass
# workspace context; these legacy no-workspace/test/admin paths must not grow.
EXPECTED_LEGACY_REFERENCES = {
    ("call:get_async_client", "core/content_engine/llm_client.py", "get_async_client()"),
    ("call:get_async_client", "core/content_engine/llm_client.py", "client = get_async_client()"),
    ("call:get_async_client", "core/content_engine/planner.py", "client = get_async_client()"),
    ("key:perplexity_api_key", "core/content_engine/workers/fact_enricher.py", "api_key = settings.perplexity_api_key"),
    ("key:perplexity_api_key", "core/content_engine/workers/linker.py", "api_key = settings.perplexity_api_key"),
    ("call:get_async_client", "core/daily_tracker/content_to_prompt.py", "client = get_async_client()"),
    ("call:get_async_client", "core/daily_tracker/query_fanout.py", "client = get_async_client()"),
    ("key:anthropic_api_key", "core/gap_analysis/engines/claude.py", "api_key = settings.anthropic_api_key"),
    ("key:google_api_key_gap_analysis", "core/gap_analysis/engines/gemini.py", "api_key = settings.google_api_key_gap_analysis"),
    ("key:openai_api_key", "core/gap_analysis/engines/openai_engine.py", "api_key = settings.openai_api_key"),
    ("call:get_async_client", "core/gap_analysis/engines/perplexity.py", "pplx_client = client if client is not None else get_async_client()"),
    ("key:openai_api_key", "core/gap_analysis/steps/s2_generate_queries.py", "api_key = settings.openai_api_key"),
    ("key:openai_api_key", "core/gap_analysis/steps/s3_search_platforms.py", "AsyncOpenAI(api_key=settings.openai_api_key)"),
    ("call:get_async_client", "core/gap_analysis/steps/s3_search_platforms.py", "shared_client = get_async_client()"),
    ("call:get_async_client", "core/gap_analysis/steps/s8_generate_report.py", "client = get_async_client()"),
    ("call:build_chat_openai_via_openrouter", "core/reddit_hil/graph.py", "return build_chat_openai_via_openrouter(settings.google_gemini_model_reddit_hil)"),
    ("call:get_async_client", "core/research/audience_persona/agents.py", "client = get_async_client()"),
    ("key:anthropic_api_key", "core/research/knowledge_base/agents.py", "client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)"),
    ("call:build_chat_openai_via_openrouter", "core/research/knowledge_base/agents.py", "model = build_chat_openai_via_openrouter(settings.research_kb_synthesis_model)"),
    ("key:openrouter_api_key", "core/research/tools/perplexity_client.py", "resolved_api_key = api_key or settings.openrouter_api_key"),
    ("key:anthropic_api_key", "core/research/voice_style_guide/agents.py", "api_key = settings.anthropic_api_key"),
    ("call:get_async_client", "core/research/voice_style_guide/agents.py", "or_client = get_async_client()"),
    ("call:get_async_client", "core/shared_tools/async_embedding_client.py", "else get_async_client()"),
    ("call:get_sync_client", "core/shared_tools/embedding_client.py", "else get_sync_client()"),
    ("key:openrouter_api_key", "core/shared_tools/openrouter_client.py", "if not settings.openrouter_api_key:"),
    ("key:openrouter_api_key", "core/shared_tools/openrouter_client.py", "api_key=settings.openrouter_api_key,"),
    ("call:get_async_client", "core/topic_discovery/agents.py", "client = get_async_client()"),
}


def _runtime_python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in RUNTIME_ROOTS:
        files.extend((PROJECT_ROOT / root_name).rglob("*.py"))
    return sorted(files)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _line_text(path: Path, lineno: int) -> str:
    return path.read_text(encoding="utf-8").splitlines()[lineno - 1].strip()


def _platform_key_references() -> set[tuple[str, str, str]]:
    refs: set[tuple[str, str, str]] = set()
    for path in _runtime_python_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "settings"
                and node.attr in PLATFORM_KEY_ATTRS
            ):
                refs.add((f"key:{node.attr}", rel, _line_text(path, node.lineno)))
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if name in SINGLETON_CLIENT_CALLS:
                    refs.add((f"call:{name}", rel, _line_text(path, node.lineno)))
    return refs


def test_no_new_platform_owned_llm_key_usage_in_runtime_code() -> None:
    actual = _platform_key_references()
    unexpected = actual - EXPECTED_LEGACY_REFERENCES

    assert not unexpected, (
        "New platform-owned LLM key or singleton OpenRouter usage found. "
        "Customer runtime must resolve workspace BYOK model config instead:\n"
        + "\n".join(f"{kind} {path}: {line}" for kind, path, line in sorted(unexpected))
    )
