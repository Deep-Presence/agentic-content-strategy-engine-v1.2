"""Step 4 — Answer Engine Optimisation (AEO) content extractability analysis.

Scores each page 0–100 on how well its content is structured for AI extraction
as answer snippets.  This is the DIFFERENTIATOR — traditional SEO tools don't
check any of this.

All checks are deterministic — no LLM calls, no network calls.

Public API::

    result, findings = analyze_aeo_readiness(html, url, config)

Composite score formula (each component 0–1, then multiplied by weight)::

    score = (
        question_heading_ratio      * 25  +
        quick_answer_hook_ratio     * 25  +
        self_contained_para_ratio   * 20  +
        paragraph_length_score      * 15  +
        content_pattern_score       * 15
    )
    score = clamp(score, 0.0, 100.0)
"""
from __future__ import annotations

import logging
from typing import Optional

from bs4 import BeautifulSoup, Tag

from core.models.site_audit import (
    AEOReadinessResult,
    AuditCheckSeverity,
    AuditDimension,
    AuditFinding,
)
from core.site_audit.checks.extractability import (
    classify_heading_as_question,
    detect_comparison_table,
    detect_definition_opening,
    detect_faq_section,
    detect_key_takeaways,
    detect_numbered_steps,
    detect_quick_answer_hook,
    detect_toc,
    is_self_contained_paragraph,
)
from core.site_audit.checks.schema_checks import infer_page_type
from core.site_audit.config import AuditConfig, DEFAULT_AUDIT_CONFIG

logger = logging.getLogger(__name__)


def _count_words(text: str) -> int:
    """Count whitespace-separated words."""
    return len(text.split())


def _compute_paragraph_length_score(
    avg_word_count: float,
    ideal_min: int,
    ideal_max: int,
) -> float:
    """Score paragraph word count closeness to the ideal range.

    Returns a score in [0.0, 1.0]:
    - 1.0 if avg_word_count is within [ideal_min, ideal_max]
    - Linearly decays to 0.0 at 0 words (below range) or 2× ideal_max (above range)

    Args:
        avg_word_count: Mean word count per paragraph.
        ideal_min: Lower bound of the ideal range.
        ideal_max: Upper bound of the ideal range.

    Returns:
        Float in [0.0, 1.0].
    """
    if avg_word_count <= 0:
        return 0.0

    # Guard against invalid config (min <= 0 would cause divide-by-zero)
    if ideal_min <= 0:
        ideal_min = 1

    if ideal_min <= avg_word_count <= ideal_max:
        return 1.0

    if avg_word_count < ideal_min:
        # Below range: linear decay from ideal_min (1.0) → 0 (0.0)
        return max(0.0, avg_word_count / ideal_min)

    # Above range: linear decay from ideal_max (1.0) → 2×ideal_max (0.0)
    upper_bound = ideal_max * 2.0
    if avg_word_count >= upper_bound:
        return 0.0
    return max(0.0, 1.0 - (avg_word_count - ideal_max) / (upper_bound - ideal_max))


def _compute_content_pattern_score(patterns: dict[str, bool]) -> float:
    """Convert detected content patterns into a capped score component.

    Scoring:
    - faq_section detected → +4
    - definition_opening detected → +3
    - key_takeaways detected → +3
    - comparison_table detected → +2
    - numbered_steps detected → +2
    - toc detected → +1

    Capped at 15 points.

    Args:
        patterns: Dict mapping pattern name → bool (detected or not).

    Returns:
        Float in [0.0, 15.0].
    """
    pattern_weights: dict[str, float] = {
        "faq_section": 4.0,
        "definition_opening": 3.0,
        "key_takeaways": 3.0,
        "comparison_table": 2.0,
        "numbered_steps": 2.0,
        "toc": 1.0,
    }
    total = sum(
        weight for key, weight in pattern_weights.items() if patterns.get(key, False)
    )
    return min(total, 15.0)


def analyze_aeo_readiness(
    html: str,
    url: str,
    config: AuditConfig = DEFAULT_AUDIT_CONFIG,
) -> tuple[AEOReadinessResult, list[AuditFinding]]:
    """Analyse a page's AEO content extractability readiness.

    Parses the HTML, runs all extractability checks, computes the composite
    snippet readiness score, and generates findings.

    Args:
        html: Raw HTML string of the page.
        url: Full URL of the page (used in findings).
        config: Audit configuration with AEO thresholds.
            Defaults to :data:`DEFAULT_AUDIT_CONFIG`.

    Returns:
        A 2-tuple of:
            - :class:`AEOReadinessResult` with all scores and pattern flags.
            - List of :class:`AuditFinding` objects for AEO issues found.
    """
    findings: list[AuditFinding] = []

    # --- Parse HTML ---
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning("analyze_aeo_readiness: HTML parse error for %s: %s", url, exc)
        return AEOReadinessResult(), findings

    # --- Collect headings ---
    all_headings: list[Tag] = []
    for tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        all_headings.extend(soup.find_all(tag_name))

    total_headings = len(all_headings)
    question_headings: list[Tag] = []
    question_heading_texts: list[str] = []

    for heading in all_headings:
        text = heading.get_text(strip=True)
        if classify_heading_as_question(text):
            question_headings.append(heading)
            question_heading_texts.append(text)

    question_heading_ratio = (
        len(question_headings) / total_headings if total_headings > 0 else 0.0
    )

    # --- Detect quick-answer hooks ---
    quick_answer_hook_count = 0
    for q_heading in question_headings:
        if detect_quick_answer_hook(q_heading, soup, config=config):
            quick_answer_hook_count += 1

    quick_answer_hook_ratio = (
        quick_answer_hook_count / len(question_headings)
        if question_headings
        else 0.0
    )

    # --- Analyse paragraphs ---
    paragraphs: list[Tag] = soup.find_all("p")
    paragraph_texts = [p.get_text(separator=" ", strip=True) for p in paragraphs]
    # Filter to paragraphs with meaningful content (≥5 words)
    meaningful_paragraphs = [t for t in paragraph_texts if _count_words(t) >= 5]

    self_contained_count = sum(
        1 for t in meaningful_paragraphs if is_self_contained_paragraph(t)
    )
    self_contained_paragraph_ratio = (
        self_contained_count / len(meaningful_paragraphs)
        if meaningful_paragraphs
        else 0.0
    )

    word_counts = [_count_words(t) for t in meaningful_paragraphs]
    avg_paragraph_word_count = (
        sum(word_counts) / len(word_counts) if word_counts else 0.0
    )

    # --- Content pattern detection ---
    first_paragraph_text = meaningful_paragraphs[0] if meaningful_paragraphs else ""
    content_patterns: dict[str, bool] = {
        "faq_section": detect_faq_section(soup),
        "definition_opening": detect_definition_opening(first_paragraph_text),
        "key_takeaways": detect_key_takeaways(soup),
        "comparison_table": detect_comparison_table(soup),
        "numbered_steps": detect_numbered_steps(soup),
        "toc": detect_toc(soup),
    }

    # --- Composite snippet readiness score ---
    paragraph_length_score = _compute_paragraph_length_score(
        avg_paragraph_word_count,
        config.aeo_ideal_paragraph_word_count_min,
        config.aeo_ideal_paragraph_word_count_max,
    )
    pattern_score = _compute_content_pattern_score(content_patterns)

    snippet_readiness_score = (
        question_heading_ratio * 25.0
        + quick_answer_hook_ratio * 25.0
        + self_contained_paragraph_ratio * 20.0
        + paragraph_length_score * 15.0
        + pattern_score  # already in [0, 15]
    )
    snippet_readiness_score = max(0.0, min(100.0, snippet_readiness_score))

    result = AEOReadinessResult(
        snippet_readiness_score=round(snippet_readiness_score, 2),
        question_heading_ratio=round(question_heading_ratio, 4),
        quick_answer_hook_count=quick_answer_hook_count,
        self_contained_paragraph_ratio=round(self_contained_paragraph_ratio, 4),
        avg_paragraph_word_count=round(avg_paragraph_word_count, 2),
        content_patterns=content_patterns,
    )

    # --- Generate findings ---

    # Low question-heading ratio
    if question_heading_ratio < config.aeo_min_question_heading_ratio:
        findings.append(
            AuditFinding(
                finding_type="low_question_heading_ratio",
                dimension=AuditDimension.extractability,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"Only {question_heading_ratio:.0%} of headings are phrased as "
                    f"questions (threshold: {config.aeo_min_question_heading_ratio:.0%}). "
                    "Question-format headings improve AI snippet extraction."
                ),
                recommendation=(
                    "Rephrase at least 30% of subheadings as questions that your "
                    "audience is actually asking (e.g. 'How does X work?' instead of "
                    "'About X'). This increases the likelihood of appearing in AI-generated answers."
                ),
                details={
                    "question_heading_ratio": question_heading_ratio,
                    "threshold": config.aeo_min_question_heading_ratio,
                    "total_headings": total_headings,
                    "question_headings": len(question_headings),
                },
            )
        )

    # Overall AEO score findings
    if snippet_readiness_score < 30:
        findings.append(
            AuditFinding(
                finding_type="poor_aeo_readiness",
                dimension=AuditDimension.extractability,
                severity=AuditCheckSeverity.high,
                url=url,
                message=(
                    f"AEO snippet readiness score is {snippet_readiness_score:.0f}/100 — "
                    "poor. This page is unlikely to be cited in AI search results."
                ),
                recommendation=(
                    "Improve content structure for AI extraction: add question-format "
                    "headings followed by direct 40-60 word answer paragraphs, ensure "
                    "paragraphs stand alone without needing prior context, and add "
                    "structured sections like FAQ, Key Takeaways, or How-To steps."
                ),
                details={"snippet_readiness_score": snippet_readiness_score},
            )
        )
    elif snippet_readiness_score < 60:
        findings.append(
            AuditFinding(
                finding_type="moderate_aeo_readiness",
                dimension=AuditDimension.extractability,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    f"AEO snippet readiness score is {snippet_readiness_score:.0f}/100 — "
                    "moderate. There is room for improvement."
                ),
                recommendation=(
                    "Enhance content structure: aim for more question headings with "
                    "direct-answer paragraphs of 40–60 words, add a FAQ section or "
                    "Key Takeaways block, and ensure paragraphs don't start with "
                    "continuity markers like 'However' or 'Additionally'."
                ),
                details={"snippet_readiness_score": snippet_readiness_score},
            )
        )

    # No self-contained answer paragraphs
    if self_contained_paragraph_ratio == 0.0 and meaningful_paragraphs:
        findings.append(
            AuditFinding(
                finding_type="no_self_contained_paragraphs",
                dimension=AuditDimension.extractability,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    "No self-contained paragraphs detected. All paragraphs either "
                    "start with continuity markers or are outside the ideal 20–80 word range."
                ),
                recommendation=(
                    "Write paragraphs that can be understood independently. Avoid "
                    "starting paragraphs with 'However', 'Additionally', 'Furthermore', "
                    "etc. Each paragraph should contain a complete thought with "
                    "20–80 words."
                ),
                details={
                    "meaningful_paragraph_count": len(meaningful_paragraphs),
                    "self_contained_count": 0,
                },
            )
        )

    # No FAQ section on FAQ-type pages
    page_type = infer_page_type(url, html)
    if page_type == "faq" and not content_patterns.get("faq_section"):
        findings.append(
            AuditFinding(
                finding_type="faq_page_missing_faq_structure",
                dimension=AuditDimension.extractability,
                severity=AuditCheckSeverity.medium,
                url=url,
                message=(
                    "This page appears to be an FAQ page (URL pattern detected) "
                    "but lacks a structured FAQ section with question headings "
                    "followed by answer paragraphs."
                ),
                recommendation=(
                    "Structure FAQ pages with clear question headings (H2/H3) "
                    "each followed immediately by a concise answer paragraph. "
                    "Consider also using a definition list (<dl>) structure."
                ),
                details={"page_type": page_type},
            )
        )

    return result, findings
