"""Linker worker — Step 3 of the v1.3 worker chain.

Resolves link placeholders in drafted content:
  - [INTERNAL-LINK: anchor text] → real URLs from s1 discovery pages
  - [EXTERNAL-LINK: anchor text] → authoritative external URLs via web search
  - [STAT: description] → sourced statistics (secondary pass)

Uses Perplexity sonar-pro for web-grounded link resolution.
All LLM calls route through LiteLLM via llm_client.llm_call().
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from core.config.settings import settings
from core.content_engine.llm_client import llm_call
from core.content_engine.prompts.linker_prompts import (
    LINKER_SYSTEM_PROMPT,
    build_linker_user_prompt,
)
from core.content_engine.tracing_v13 import create_span, end_span, extract_provider, log_generation
from core.content_engine.utils import truncate_to_token_limit
from core.models.content_generation import ContentBrief, ContentDraft, LinkedDraft

logger = logging.getLogger(__name__)


async def link_content(
    draft: ContentDraft,
    brief: ContentBrief,
    company_name: str,
    domain: str,
    site_pages: list[str] | None = None,
    *,
    trace: Optional[object] = None,
    company_slug: str = "",
) -> LinkedDraft:
    """Resolve link placeholders in a draft using Perplexity sonar-pro.

    Args:
        draft: The drafted content with link placeholders.
        brief: Original content brief for context.
        company_name: Company name for search context.
        domain: Company domain.
        site_pages: List of known site page URLs for internal linking.
        trace: LangSmith trace for instrumentation.

    Returns:
        LinkedDraft with resolved links and counts.
    """
    model = settings.content_engine_v13_linker_model
    span = create_span(
        trace, f"linker/{brief.brief_id}",
        metadata={"brief_id": brief.brief_id, "model": model},
        input_data={
            "brief_id": brief.brief_id,
            "title": brief.title,
            "company_name": company_name,
            "domain": domain,
            "draft_word_count": draft.word_count,
            "site_pages_count": len(site_pages) if site_pages else 0,
        },
    )

    # Check for API key — graceful degradation
    api_key = settings.perplexity_api_key
    if not api_key:
        logger.warning("PERPLEXITY_API_KEY not set — skipping link resolution")
        end_span(span, output={"skipped": "no API key"})
        return LinkedDraft(
            brief_id=draft.brief_id,
            title=draft.title,
            markdown=draft.markdown,
            word_count=draft.word_count,
            internal_links_added=0,
            external_links_added=0,
            stats_resolved=0,
        )

    user_prompt = build_linker_user_prompt(
        draft_markdown=draft.markdown,
        title=brief.title,
        key_topics=brief.key_topics,
        company_name=company_name,
        domain=domain,
        site_pages=site_pages,
    )
    # Truncate to sonar-pro context budget (127k tokens); leave headroom for system + response
    user_prompt = truncate_to_token_limit(
        user_prompt, max_tokens=120_000, label="linker_user"
    )

    try:
        response = await llm_call(
            model=model,
            system=LINKER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=8192,
            metadata={
                "agent": "linker",
                "brief_id": brief.brief_id,
                "pipeline": "content_engine",
                "pipeline_step": "linker",
                "provider": extract_provider(model),
                "model": model,
                "company_slug": company_slug,
            },
            max_retries=2,
            base_delay=3.0,
        )

        linked_text = response.content

        # Clean up code fences
        if linked_text.startswith("```markdown"):
            linked_text = linked_text[len("```markdown"):].strip()
        if linked_text.startswith("```"):
            linked_text = linked_text[3:].strip()
        if linked_text.endswith("```"):
            linked_text = linked_text[:-3].strip()

        # Count links added
        internal_links = _count_internal_links(linked_text, domain)
        external_links = _count_external_links(linked_text, domain)
        stats_resolved = _count_stats_resolved(draft.markdown, linked_text)

        word_count = len(linked_text.split())

        log_generation(
            parent=span,
            name="linker",
            model=model,
            input_text=user_prompt[:3000],
            output_text=linked_text[:3000],
            usage={
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            },
        )
        end_span(span, output={
            "internal_links_added": internal_links,
            "external_links_added": external_links,
            "stats_resolved": stats_resolved,
            "word_count": word_count,
        })

        logger.info(
            "Linker: %s → %d internal, %d external links, %d stats resolved, %d words",
            brief.brief_id,
            internal_links,
            external_links,
            stats_resolved,
            word_count,
        )

        return LinkedDraft(
            brief_id=draft.brief_id,
            title=draft.title,
            markdown=linked_text,
            word_count=word_count,
            internal_links_added=internal_links,
            external_links_added=external_links,
            stats_resolved=stats_resolved,
        )
    except Exception as exc:
        end_span(span, error=str(exc)[:500])
        raise


def _count_internal_links(markdown: str, domain: str) -> int:
    """Count markdown links pointing to the company's domain."""
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
    count = 0
    for _, url in pattern.findall(markdown):
        if domain in url:
            count += 1
    return count


def _count_external_links(markdown: str, domain: str) -> int:
    """Count markdown links pointing to external domains."""
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
    count = 0
    for _, url in pattern.findall(markdown):
        if domain not in url:
            count += 1
    return count


def _count_stats_resolved(original: str, linked: str) -> int:
    """Count how many [STAT: ...] placeholders were resolved."""
    original_stats = len(re.findall(r"\[STAT:\s*[^\]]+\]", original))
    remaining_stats = len(re.findall(r"\[STAT:\s*[^\]]+\]", linked))
    return max(0, original_stats - remaining_stats)
