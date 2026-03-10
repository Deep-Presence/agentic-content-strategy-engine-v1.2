"""Structural evaluator — deterministic content quality checks.

Pure Python evaluation — no LLM calls.

v2.0: Weighted scoring with hard gates. 14 checks total:
- 4 hard gates (must pass, score capped at 0.5 if any fail)
- 10 soft weighted checks (conditional — only count when target > 0)
- 6 new checks: paragraph_length, sentence_length, faq_presence,
  table_presence, self_contained_claims, bullet_density
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.content_engine.tracing_v13 import create_span, end_span, log_score
from core.models.content_generation import (
    ContentBrief,
    DimensionResult,
    FormattedContent,
)


# ---------------------------------------------------------------------------
# Hard gate checks (must pass — score capped at 0.5 if any fail)
# ---------------------------------------------------------------------------


def _check_word_count(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check if word count is within the brief's range."""
    min_wc, max_wc = brief.word_count_range
    wc = content.word_count
    passed = min_wc <= wc <= max_wc
    feedback = ""
    if wc < min_wc:
        feedback = f"Word count {wc} is below minimum {min_wc}. Add {min_wc - wc} more words."
    elif wc > max_wc:
        feedback = f"Word count {wc} exceeds maximum {max_wc}. Trim {wc - max_wc} words."
    return passed, feedback, {"word_count": wc, "range": [min_wc, max_wc]}


def _check_heading_hierarchy(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check that heading levels don't skip (e.g., H2 → H4 without H3)."""
    lines = content.markdown.split("\n")
    headings = []
    for line in lines:
        match = re.match(r"^(#{1,6})\s", line)
        if match:
            headings.append(len(match.group(1)))

    if len(headings) < 2:
        return True, "", {"headings": headings}

    for i in range(1, len(headings)):
        if headings[i] > headings[i - 1] + 1:
            return (
                False,
                f"Heading hierarchy skip: H{headings[i-1]} → H{headings[i]}. Don't skip levels.",
                {"headings": headings},
            )
    return True, "", {"headings": headings}


def _check_no_empty_sections(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check for empty sections (heading immediately followed by another heading)."""
    lines = content.markdown.split("\n")
    empty_sections = []

    for i in range(len(lines) - 1):
        if re.match(r"^#{1,6}\s", lines[i]):
            # Look ahead for next non-empty line
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.match(r"^#{1,6}\s", lines[j]):
                empty_sections.append(lines[i].strip())

    passed = len(empty_sections) == 0
    feedback = ""
    if not passed:
        feedback = f"Empty sections found: {', '.join(empty_sections[:3])}. Add content under each heading."
    return passed, feedback, {"empty_sections": empty_sections}


def _check_required_elements(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check that required structural elements are present."""
    missing = []

    for elem in brief.required_structural_elements:
        elem_lower = elem.lower()
        if elem_lower == "headers" and content.header_count == 0:
            missing.append(elem)
        elif elem_lower == "lists" and content.list_count == 0:
            missing.append(elem)
        elif elem_lower == "statistics" and content.stat_count == 0:
            missing.append(elem)
        elif elem_lower == "citations" and content.citation_count == 0:
            missing.append(elem)

    passed = len(missing) == 0
    feedback = ""
    if not passed:
        feedback = f"Missing required elements: {', '.join(missing)}"
    return passed, feedback, {"missing": missing, "required": brief.required_structural_elements}


# Hard gates list
_HARD_GATES = [
    ("word_count", _check_word_count),
    ("heading_hierarchy", _check_heading_hierarchy),
    ("no_empty_sections", _check_no_empty_sections),
    ("required_elements", _check_required_elements),
]


# ---------------------------------------------------------------------------
# Soft weighted checks (contribute to score, conditional)
# ---------------------------------------------------------------------------


def _check_headers(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check minimum header count."""
    target = brief.structural_targets.min_headers
    actual = content.header_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} headers — need at least {target}."
    return passed, feedback, {"actual": actual, "target": target}


def _check_lists(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check minimum list count."""
    target = brief.structural_targets.min_lists
    actual = content.list_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} list items — need at least {target}."
    return passed, feedback, {"actual": actual, "target": target}


def _check_citations(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check minimum citation count."""
    target = brief.structural_targets.min_citations
    actual = content.citation_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} citations — need at least {target}."
    return passed, feedback, {"actual": actual, "target": target}


def _check_stats(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check for presence of statistics/data points."""
    target = brief.structural_targets.min_stats
    actual = content.stat_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} statistics — need at least {target}. Add quantitative evidence."
    return passed, feedback, {"actual": actual, "target": target}


def _check_paragraph_length(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check avg paragraph word count vs target (±30% tolerance)."""
    target = brief.structural_targets.avg_paragraph_word_count
    if target <= 0:
        return True, "", {"skipped": True, "reason": "no target set"}

    # Split into paragraphs (non-empty, non-heading, non-list lines grouped)
    paragraphs = _extract_paragraphs(content.markdown)
    if not paragraphs:
        return True, "", {"paragraph_count": 0}

    word_counts = [len(p.split()) for p in paragraphs]
    avg_wc = sum(word_counts) / len(word_counts)

    # ±30% tolerance
    lower = target * 0.7
    upper = target * 1.3
    passed = lower <= avg_wc <= upper

    feedback = ""
    if not passed:
        if avg_wc < lower:
            feedback = f"Avg paragraph length {avg_wc:.0f} words is too short (target: {target}). Expand paragraphs with more supporting detail."
        else:
            feedback = f"Avg paragraph length {avg_wc:.0f} words is too long (target: {target}). Break into smaller, self-contained paragraphs."

    return passed, feedback, {
        "avg_paragraph_word_count": round(avg_wc, 1),
        "target": target,
        "paragraph_count": len(paragraphs),
    }


def _check_sentence_length(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Flag if >10% of sentences exceed 30 words."""
    paragraphs = _extract_paragraphs(content.markdown)
    if not paragraphs:
        return True, "", {"sentence_count": 0}

    text = " ".join(paragraphs)
    sentences = re.split(r'[.!?]+\s+', text)
    sentences = [s for s in sentences if s.strip()]

    if not sentences:
        return True, "", {"sentence_count": 0}

    long_count = sum(1 for s in sentences if len(s.split()) > 30)
    ratio = long_count / len(sentences)
    passed = ratio <= 0.10

    feedback = ""
    if not passed:
        feedback = (
            f"{long_count}/{len(sentences)} sentences ({ratio:.0%}) exceed 30 words. "
            "Break long sentences for readability."
        )

    return passed, feedback, {
        "sentence_count": len(sentences),
        "long_sentence_count": long_count,
        "long_sentence_ratio": round(ratio, 3),
    }


def _check_faq_presence(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """If faq_rate > 0.3, require FAQ section."""
    faq_rate = brief.structural_targets.faq_rate
    if faq_rate <= 0.3:
        return True, "", {"skipped": True, "reason": f"faq_rate={faq_rate} <= 0.3"}

    md_lower = content.markdown.lower()
    has_faq = bool(re.search(r"(faq|frequently\s+asked|common\s+questions)", md_lower))

    feedback = ""
    if not has_faq:
        feedback = (
            f"FAQ section missing but {faq_rate:.0%} of cited content has FAQs. "
            "Add a Frequently Asked Questions section."
        )

    return has_faq, feedback, {"faq_rate": faq_rate, "has_faq": has_faq}


def _check_table_presence(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """If table_rate > 0.3, require markdown table."""
    table_rate = brief.structural_targets.table_rate
    if table_rate <= 0.3:
        return True, "", {"skipped": True, "reason": f"table_rate={table_rate} <= 0.3"}

    has_table = bool(re.search(r"\|.+\|.+\|", content.markdown))

    feedback = ""
    if not has_table:
        feedback = (
            f"Table missing but {table_rate:.0%} of cited content has tables. "
            "Add a comparison or data table."
        )

    return has_table, feedback, {"table_rate": table_rate, "has_table": has_table}


def _check_self_contained_claims(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Heuristic: count paragraphs of 20-150 words with stat or definitive statement."""
    target = brief.structural_targets.min_self_contained_claims
    if target <= 0:
        return True, "", {"skipped": True, "reason": "no target set"}

    paragraphs = _extract_paragraphs(content.markdown)
    claim_count = 0
    for p in paragraphs:
        wc = len(p.split())
        if 20 <= wc <= 150:
            # Heuristic: has a stat, percentage, or definitive statement pattern
            if re.search(r'\d+[%$]|\$\d+|\d+\s*(million|billion|percent)|according to|research shows|studies show|data shows', p, re.IGNORECASE):
                claim_count += 1

    passed = claim_count >= target
    feedback = ""
    if not passed:
        feedback = (
            f"Only {claim_count} self-contained claims detected — need at least {target}. "
            "Add more paragraphs (20-150 words) with specific data or definitive statements."
        )

    return passed, feedback, {"claim_count": claim_count, "target": target}


def _check_bullet_density(content: FormattedContent, brief: ContentBrief) -> Tuple[bool, str, Dict[str, Any]]:
    """Check avg bullets per list block vs min_bullets_per_list."""
    target = brief.structural_targets.min_bullets_per_list
    if target <= 0:
        return True, "", {"skipped": True, "reason": "no target set"}

    # Find list blocks (consecutive list lines)
    lines = content.markdown.split("\n")
    list_blocks: List[List[str]] = []
    current_block: List[str] = []

    for line in lines:
        if re.match(r"^\s*[-*+]\s", line) or re.match(r"^\s*\d+\.\s", line):
            current_block.append(line)
        else:
            if current_block:
                list_blocks.append(current_block)
                current_block = []
    if current_block:
        list_blocks.append(current_block)

    if not list_blocks:
        # No lists at all — if list count target > 0, this is caught by _check_lists
        return True, "", {"list_block_count": 0}

    avg_bullets = sum(len(b) for b in list_blocks) / len(list_blocks)
    passed = avg_bullets >= target

    feedback = ""
    if not passed:
        feedback = (
            f"Avg {avg_bullets:.1f} bullets per list — need at least {target}. "
            "Expand lists with more items."
        )

    return passed, feedback, {
        "list_block_count": len(list_blocks),
        "avg_bullets_per_list": round(avg_bullets, 1),
        "target": target,
    }


# Soft checks with weights
_SOFT_CHECKS = [
    ("header_count", _check_headers, 0.12),
    ("list_count", _check_lists, 0.08),
    ("citation_count", _check_citations, 0.12),
    ("stat_presence", _check_stats, 0.10),
    ("paragraph_length", _check_paragraph_length, 0.12),
    ("sentence_length", _check_sentence_length, 0.08),
    ("faq_presence", _check_faq_presence, 0.10),
    ("table_presence", _check_table_presence, 0.08),
    ("self_contained_claims", _check_self_contained_claims, 0.12),
    ("bullet_density", _check_bullet_density, 0.08),
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _extract_paragraphs(markdown: str) -> List[str]:
    """Extract content paragraphs from markdown (excluding headers, lists, tables)."""
    lines = markdown.split("\n")
    paragraphs = []
    current = []

    for line in lines:
        stripped = line.strip()
        # Skip headers, list items, table rows, empty lines
        if (
            re.match(r"^#{1,6}\s", stripped)
            or re.match(r"^\s*[-*+]\s", stripped)
            or re.match(r"^\s*\d+\.\s", stripped)
            or re.match(r"^\|", stripped)
            or not stripped
        ):
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))

    # Filter out very short fragments (< 10 words)
    return [p for p in paragraphs if len(p.split()) >= 10]


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------


def evaluate_structural(
    content: FormattedContent,
    brief: ContentBrief,
    *,
    trace: Optional[object] = None,
) -> DimensionResult:
    """Run all structural checks with weighted scoring and hard gates.

    Architecture:
    - Hard gates (4): Must all pass. If any fail, score is capped at 0.5.
    - Soft weighted checks (10): Each has a weight. Conditional checks (where
      the target is 0 or rate <= threshold) are skipped and don't affect the score.
    - Final score = soft_weighted_score (capped at 0.5 if hard gates fail).
    - Pass threshold: score >= 0.70.

    Args:
        content: The formatted content to evaluate.
        brief: The content brief with targets.
        trace: Trace span for instrumentation.

    Returns:
        DimensionResult with structural evaluation.
    """
    span = create_span(
        trace, "structural_check",
        metadata={"brief_id": content.brief_id},
        input={
            "word_count": content.word_count,
            "header_count": content.header_count,
            "list_count": content.list_count,
            "stat_count": content.stat_count,
            "citation_count": content.citation_count,
        },
    )

    results = {}
    feedbacks = []

    # Run hard gates
    all_gates_passed = True
    for check_name, check_fn in _HARD_GATES:
        passed, feedback, details = check_fn(content, brief)
        results[check_name] = {"passed": passed, "feedback": feedback, "hard_gate": True, **details}
        if not passed:
            all_gates_passed = False
            if feedback:
                feedbacks.append(f"[HARD GATE] {feedback}")

    # Run soft weighted checks
    total_weight = 0.0
    weighted_score = 0.0

    for check_name, check_fn, weight in _SOFT_CHECKS:
        passed, feedback, details = check_fn(content, brief)
        is_skipped = details.get("skipped", False)
        results[check_name] = {"passed": passed, "feedback": feedback, "weight": weight, "skipped": is_skipped, **details}

        if is_skipped:
            # Don't count skipped checks in denominator
            continue

        total_weight += weight
        if passed:
            weighted_score += weight
        elif feedback:
            feedbacks.append(feedback)

    # Compute final score
    if total_weight > 0:
        soft_score = weighted_score / total_weight
    else:
        soft_score = 1.0  # All soft checks skipped

    # Cap at 0.5 if any hard gate fails
    if not all_gates_passed:
        score = min(soft_score, 0.5)
    else:
        score = soft_score

    overall_passed = score >= 0.70

    # Logging
    failed_checks = [
        name for name in results
        if not results[name].get("passed", True) and not results[name].get("skipped", False)
    ]
    log_score(span, "structural_score", round(score, 3))
    end_span(span, output={
        "score": round(score, 3),
        "passed": overall_passed,
        "hard_gates_passed": all_gates_passed,
        "soft_score": round(soft_score, 3),
        "active_soft_weight": round(total_weight, 3),
        "failed_checks": failed_checks,
    })

    return DimensionResult(
        dimension="structural",
        passed=overall_passed,
        score=round(score, 3),
        feedback=" | ".join(feedbacks) if feedbacks else "All structural checks passed.",
        details=results,
    )
