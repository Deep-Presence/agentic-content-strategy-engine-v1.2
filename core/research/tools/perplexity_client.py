"""
Perplexity Deep Research client.

Uses sonar-deep-research for comprehensive web-grounded research with citations.
See https://docs.perplexity.ai/docs/getting-started/overview
"""
from typing import Any, Dict, Optional

from core.config.settings import settings


def _client(timeout_s: float = 300.0):
    """Lazy import to avoid top-level dependency failure.

    Args:
        timeout_s: HTTP-level timeout in seconds. Ensures the underlying
            thread terminates when asyncio.wait_for cancels the coroutine.
    """
    from perplexity import Perplexity

    api_key = settings.perplexity_api_key
    if not api_key:
        raise RuntimeError(
            "PERPLEXITY_API_KEY is not set. Get your key at https://perplexity.ai/account/api"
        )
    try:
        return Perplexity(api_key=api_key, timeout=timeout_s)
    except TypeError:
        # SDK version doesn't support timeout param — fall back gracefully
        return Perplexity(api_key=api_key)


def research(
    query: str,
    max_results: int = 8,
    search_depth: str = "advanced",
    include_raw_content: bool = False,
    include_answer: bool = True,
    timeout_s: float = 300.0,
    model: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Deep web research using Perplexity sonar-deep-research model.

    Conducts autonomous multi-step retrieval, synthesis, and reasoning.
    Returns research text with inline citations [1], [2], etc.

    Args:
        model: Override the default Perplexity model. If None, uses
            settings.perplexity_deep_research_model.
    """
    client = _client(timeout_s=timeout_s)
    model = model or settings.perplexity_deep_research_model

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
            stream=False,
        )
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Authorization" in msg or "invalid" in msg.lower():
            raise RuntimeError(
                "Perplexity API key invalid or expired. "
                "Check PERPLEXITY_API_KEY at https://perplexity.ai/account/api"
            ) from e
        if "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
            raise RuntimeError(
                "Perplexity API rate limit or quota exceeded. "
                "Check usage at https://perplexity.ai/account/api"
            ) from e
        raise

    content = ""
    if completion.choices:
        msg = completion.choices[0].message
        content = getattr(msg, "content", None) or ""

    citations = getattr(completion, "citations", None)
    if citations and isinstance(citations, list):
        cited = "\n\nSources:\n" + "\n".join(f"[{i+1}] {c}" for i, c in enumerate(citations))
        content = (content or "").rstrip() + "\n" + cited

    return content or ""


def search(
    query: str,
    max_results: int = 8,
    search_depth: str = "advanced",
    include_raw_content: bool = False,
    include_answer: bool = True,
    timeout_s: float = 300.0,
    model: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Alias for research (Perplexity Deep Research covers both search and deep research)."""
    return research(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_raw_content=include_raw_content,
        include_answer=include_answer,
        timeout_s=timeout_s,
        model=model,
        **kwargs,
    )
