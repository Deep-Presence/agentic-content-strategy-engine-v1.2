"""Topic-assignment cannibalization scoring on top of inventory similarity hits."""
from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse

from core.config.settings import settings
from core.content_inventory.models import CannibalizationMatch
from core.models.topic_discovery import IntentType, TopicAssignment

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "vs", "with", "your",
}
_COMMERCIAL_HINTS = {
    "best", "compare", "comparison", "competitor", "competitors", "pricing",
    "review", "reviews", "versus", "vs", "alternative", "alternatives",
}
_INFORMATIONAL_HINTS = {
    "guide", "how", "tutorial", "what", "why", "template", "examples",
    "checklist", "playbook", "workflow",
}
_NAVIGATIONAL_HINTS = {
    "api", "dashboard", "docs", "documentation", "integrations", "login",
}
_TRANSACTIONAL_HINTS = {
    "book", "buy", "demo", "get", "quote", "request", "signup", "trial",
}
_GUIDE_FAMILY = {
    "comprehensive_guide", "explainer", "guide", "how_to", "how_to_guide",
    "long_blog", "long_form_article", "pillar_page", "tutorial",
}
_COMPARISON_FAMILY = {"comparison", "comparison_guide", "listicle"}
_CASE_STUDY_FAMILY = {"case_study"}
_LANDING_FAMILY = {"docs", "landing_page", "navigational"}


def assess_assignment_cannibalization(
    assignment: TopicAssignment,
    matches: list[CannibalizationMatch],
) -> dict[str, Any]:
    """Return planner-ready cannibalization metadata for one assignment."""
    if not matches:
        return {
            "cannibalization_risk": 0.0,
            "cannibalization_risk_score": 0.0,
            "cannibalization_risk_level": "none",
            "cannibalization_recommended_action": "safe_to_create_new",
            "cannibalization_reasons": [],
            "cannibalization_matches": [],
        }

    scored_matches = sorted(
        (_score_match(assignment, match) for match in matches),
        key=lambda item: (item["risk_score"], item["similarity"]),
        reverse=True,
    )
    top_match = scored_matches[0]
    max_similarity = max(match.similarity for match in matches)
    risk_score = round(top_match["risk_score"], 4)
    risk_level = _classify_risk_level(max_similarity=max_similarity, risk_score=risk_score)

    return {
        "cannibalization_risk": round(max_similarity, 4),
        "cannibalization_risk_score": risk_score,
        "cannibalization_risk_level": risk_level,
        "cannibalization_recommended_action": _recommended_action(
            risk_level,
            top_match["signals"],
        ),
        "cannibalization_reasons": top_match["reasons"][:3],
        "cannibalization_matches": [
            {
                "inventory_id": match["inventory_id"],
                "url": match["url"],
                "title": match["title"],
                "similarity": round(match["similarity"], 4),
                "word_count": match["word_count"],
                "content_type": match["content_type"],
                "risk_score": round(match["risk_score"], 4),
                "risk_level": match["risk_level"],
                "reasons": match["reasons"][:3],
                "signals": {
                    key: round(value, 4)
                    for key, value in match["signals"].items()
                },
            }
            for match in scored_matches[:settings.td_cannibalization_max_matches]
        ],
    }


def _score_match(
    assignment: TopicAssignment,
    match: CannibalizationMatch,
) -> dict[str, Any]:
    assignment_tokens = _assignment_tokens(assignment)
    page_tokens = _page_tokens(match)
    lexical_overlap = _jaccard(assignment_tokens, page_tokens)

    assignment_intent = assignment.intent_type.value
    page_intent = _infer_intent(
        match.title,
        match.url,
        getattr(match, "content_preview", ""),
    )
    intent_overlap = _intent_overlap_score(assignment_intent, page_intent)

    assignment_format = _normalize_assignment_format(assignment.metadata.get("content_format"))
    page_format = _normalize_page_format(match)
    format_overlap = _format_overlap_score(assignment_format, page_format)

    risk_score = min(
        1.0,
        (match.similarity * 0.78)
        + (lexical_overlap * 0.15)
        + (intent_overlap * 0.07)
        + (format_overlap * 0.03),
    )
    if (
        match.similarity >= settings.td_cannibalization_high_risk_threshold
        and (lexical_overlap >= 0.1 or intent_overlap >= 0.75)
    ):
        risk_score = max(
            risk_score,
            min(
                1.0,
                settings.td_cannibalization_high_risk_threshold
                + ((match.similarity - settings.td_cannibalization_high_risk_threshold) * 0.5),
            ),
        )
    risk_level = _classify_risk_level(
        max_similarity=match.similarity,
        risk_score=risk_score,
    )

    signals = {
        "semantic_similarity": match.similarity,
        "lexical_overlap": lexical_overlap,
        "intent_overlap": intent_overlap,
        "format_overlap": format_overlap,
    }

    reasons: list[str] = [
        f"{round(match.similarity * 100)}% semantic similarity to an existing published page.",
    ]
    if lexical_overlap >= 0.2:
        reasons.append("Title, URL, or keyword overlap suggests the same search demand.")
    if intent_overlap >= 0.75 and page_intent:
        reasons.append(
            f"Both the assignment and existing page look {page_intent.replace('_', ' ')} in intent."
        )
    if format_overlap >= 1.0 and assignment_format:
        reasons.append(
            f"Both assets map to a similar {assignment_format.replace('_', ' ')} format."
        )
    if risk_level == "medium" and not lexical_overlap >= 0.2:
        reasons.append("Semantic similarity is real, but the surface angle still appears distinguishable.")

    return {
        "inventory_id": match.inventory_id,
        "url": match.url,
        "title": match.title,
        "similarity": match.similarity,
        "word_count": match.word_count,
        "content_type": match.content_type_detected or "",
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reasons": reasons,
        "signals": signals,
    }


def _classify_risk_level(*, max_similarity: float, risk_score: float) -> str:
    if max_similarity >= settings.td_cannibalization_high_risk_threshold:
        return "high"
    if (
        max_similarity >= settings.td_cannibalization_threshold
        or risk_score >= settings.td_cannibalization_medium_risk_threshold
    ):
        return "medium"
    if max_similarity > 0:
        return "low"
    return "none"


def _recommended_action(risk_level: str, signals: dict[str, float]) -> str:
    if risk_level == "high":
        if signals["lexical_overlap"] >= 0.2 or signals["intent_overlap"] >= 0.75:
            return "merge_or_refresh_existing"
        return "optimize_existing"
    if risk_level == "medium":
        return "differentiate_angle"
    return "safe_to_create_new"


def _assignment_tokens(assignment: TopicAssignment) -> set[str]:
    metadata = assignment.metadata or {}
    parts = [
        assignment.topic_text,
        str(metadata.get("description") or ""),
        *_extract_keyword_strings(metadata.get("target_keywords")),
    ]
    return _tokenize(parts)


def _page_tokens(match: CannibalizationMatch) -> set[str]:
    parsed = urlparse(match.url)
    path = parsed.path.replace("-", " ").replace("/", " ")
    return _tokenize([match.title, path, getattr(match, "content_preview", "")])


def _tokenize(parts: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in _TOKEN_RE.findall((part or "").lower()):
            if len(token) < 3 or token in _STOP_WORDS:
                continue
            tokens.add(token)
    return tokens


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _extract_keyword_strings(raw_keywords: Any) -> list[str]:
    if isinstance(raw_keywords, list):
        return [str(value) for value in raw_keywords if value]
    if isinstance(raw_keywords, dict):
        parts: list[str] = []
        primary = raw_keywords.get("primary")
        if primary:
            parts.append(str(primary))
        secondary = raw_keywords.get("secondary")
        if isinstance(secondary, list):
            parts.extend(str(value) for value in secondary if value)
        return parts
    return []


def _infer_intent(*parts: str) -> str | None:
    tokens = _tokenize(parts)
    if not tokens:
        return None
    if tokens & _COMMERCIAL_HINTS:
        return IntentType.commercial.value
    if tokens & _TRANSACTIONAL_HINTS:
        return IntentType.transactional.value
    if tokens & _NAVIGATIONAL_HINTS:
        return IntentType.navigational.value
    if tokens & _INFORMATIONAL_HINTS:
        return IntentType.informational.value
    return None


def _intent_overlap_score(assignment_intent: str, page_intent: str | None) -> float:
    if page_intent is None:
        return 0.35
    if page_intent == assignment_intent:
        return 1.0
    if {page_intent, assignment_intent} <= {
        IntentType.commercial.value,
        IntentType.transactional.value,
    }:
        return 0.65
    return 0.0


def _normalize_assignment_format(raw_value: Any) -> str | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    return _format_family(raw_value.strip().lower().replace(" ", "_"))


def _normalize_page_format(match: CannibalizationMatch) -> str | None:
    content_type = getattr(match, "content_type_detected", "")
    if content_type:
        return _format_family(content_type.lower())

    title = f"{match.title} {match.url}".lower()
    if any(token in title for token in (" vs ", "compare", "comparison", "alternatives")):
        return "comparison"
    if "case" in title and "study" in title:
        return "case_study"
    if any(token in title for token in ("how to", "guide", "tutorial", "checklist", "playbook")):
        return "guide"
    return None


def _format_family(raw_value: str) -> str:
    if raw_value in _GUIDE_FAMILY:
        return "guide"
    if raw_value in _COMPARISON_FAMILY:
        return "comparison"
    if raw_value in _CASE_STUDY_FAMILY:
        return "case_study"
    if raw_value in _LANDING_FAMILY:
        return "landing_page"
    return raw_value


def _format_overlap_score(
    assignment_format: str | None,
    page_format: str | None,
) -> float:
    if assignment_format is None or page_format is None:
        return 0.0
    if assignment_format == page_format:
        return 1.0
    if {assignment_format, page_format} <= {"guide", "landing_page"}:
        return 0.35
    return 0.0
