"""Structural evaluator — deterministic content quality checks.

Pure Python evaluation — no LLM calls. Checks 8 structural criteria
against the brief's targets and thresholds.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.content_engine.tracing import create_span, end_span, log_score
from core.models.content_generation import (
    ContentBrief,
    DimensionResult,
    FormattedContent,
)


def _check_word_count(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
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


def _check_headers(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
    """Check minimum header count."""
    target = brief.structural_targets.min_headers
    actual = content.header_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} headers — need at least {target}."
    return passed, feedback, {"actual": actual, "target": target}


def _check_lists(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
    """Check minimum list count."""
    target = brief.structural_targets.min_lists
    actual = content.list_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} list items — need at least {target}."
    return passed, feedback, {"actual": actual, "target": target}


def _check_citations(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
    """Check minimum citation count."""
    target = brief.structural_targets.min_citations
    actual = content.citation_count
    passed = actual >= target
    feedback = "" if passed else f"Only {actual} citations — need at least {target}."
    return passed, feedback, {"actual": actual, "target": target}


def _check_stats(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
    """Check for presence of statistics/data points."""
    actual = content.stat_count
    passed = actual >= 1
    feedback = "" if passed else "No statistics or data points found. Add quantitative evidence."
    return passed, feedback, {"actual": actual}


def _check_heading_hierarchy(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
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


def _check_no_empty_sections(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
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


def _check_required_elements(content: FormattedContent, brief: ContentBrief) -> tuple[bool, str, Dict[str, Any]]:
    """Check that required structural elements are present."""
    missing = []
    md_lower = content.markdown.lower()

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


_CHECKS = [
    ("word_count", _check_word_count),
    ("header_count", _check_headers),
    ("list_count", _check_lists),
    ("citation_count", _check_citations),
    ("stat_presence", _check_stats),
    ("heading_hierarchy", _check_heading_hierarchy),
    ("no_empty_sections", _check_no_empty_sections),
    ("required_elements", _check_required_elements),
]


def evaluate_structural(
    content: FormattedContent,
    brief: ContentBrief,
    *,
    trace: Optional[object] = None,
) -> DimensionResult:
    """Run all 8 structural checks and return an aggregate result.

    Score = (passed_checks / total_checks). Passes if score >= 0.8.

    Args:
        content: The formatted content to evaluate.
        brief: The content brief with targets.
        trace: Langfuse trace for instrumentation.

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
    passed_count = 0

    for check_name, check_fn in _CHECKS:
        passed, feedback, details = check_fn(content, brief)
        results[check_name] = {"passed": passed, "feedback": feedback, **details}
        if passed:
            passed_count += 1
        elif feedback:
            feedbacks.append(feedback)

    score = passed_count / len(_CHECKS) if _CHECKS else 0.0
    overall_passed = score >= 0.8

    failed_checks = [name for name, _ in _CHECKS if not results[name]["passed"]]
    log_score(trace, "structural_score", round(score, 3))
    end_span(span, output={
        "score": round(score, 3),
        "passed": overall_passed,
        "passed_checks": passed_count,
        "total_checks": len(_CHECKS),
        "failed_checks": failed_checks,
    })

    return DimensionResult(
        dimension="structural",
        passed=overall_passed,
        score=round(score, 3),
        feedback=" | ".join(feedbacks) if feedbacks else "All structural checks passed.",
        details=results,
    )
