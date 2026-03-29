"""
Perplexity Deep Research client via OpenRouter.

Uses OpenRouter to route to Perplexity sonar-deep-research for comprehensive
web-grounded research with citations.

The sync OpenAI client is used because all callers wrap this in asyncio.to_thread().
"""
from typing import Any, Optional

import openai

from core.config.settings import settings


def _client(timeout_s: float = 300.0):
    """Create a sync OpenAI client pointed at OpenRouter.

    Args:
        timeout_s: HTTP-level timeout in seconds. Ensures the underlying
            thread terminates when asyncio.wait_for cancels the coroutine.
    """
    api_key = settings.openrouter_api_key
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Get your key at https://openrouter.ai/settings/keys"
        )
    return openai.OpenAI(
        base_url=settings.openrouter_base_url,
        api_key=api_key,
        timeout=timeout_s,
        max_retries=0,
    )


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
    Deep web research using Perplexity sonar-deep-research model via OpenRouter.

    Conducts autonomous multi-step retrieval, synthesis, and reasoning.
    Returns research text with inline citations [1], [2], etc.

    Args:
        model: Override the default Perplexity model. If None, uses
            settings.perplexity_deep_research_model.
    """
    client = _client(timeout_s=timeout_s)
    model = model or settings.perplexity_deep_research_model

    # Ensure provider prefix for OpenRouter routing
    if "/" not in model and model.startswith("sonar"):
        model = f"perplexity/{model}"

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
        )
    except openai.AuthenticationError as e:
        raise RuntimeError(
            "OpenRouter API key invalid or expired. "
            "Check OPENROUTER_API_KEY at https://openrouter.ai/settings/keys"
        ) from e
    except openai.RateLimitError as e:
        raise RuntimeError(
            "OpenRouter rate limit or quota exceeded. "
            "Check usage at https://openrouter.ai/settings/keys"
        ) from e

    content = ""
    if completion.choices:
        msg = completion.choices[0].message
        content = getattr(msg, "content", None) or ""

    # Extract citations — OpenRouter passes through Perplexity's citations field.
    # The openai SDK stores unknown response fields in model_extra.
    citations = getattr(completion, "citations", None)
    if not citations:
        extra = getattr(completion, "model_extra", None)
        if isinstance(extra, dict):
            citations = extra.get("citations")

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
