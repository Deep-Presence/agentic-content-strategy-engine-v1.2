"""Topic-assignment cannibalization scoring on top of inventory similarity hits."""
from __future__ import annotations

import re
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

import structlog

from core.config.settings import settings
from core.content_inventory.models import CannibalizationMatch
from core.models.topic_discovery import IntentType, TopicAssignment
from core.shared_tools.structured_logging import scoped_bind
from core.shared_tools.tracing import create_span, end_span

from core.topic_discovery.db_ops import _db_row_to_pydantic_assignment

logger = structlog.get_logger(__name__)

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
_CANNIBALIZATION_METADATA_KEYS = (
    "cannibalization_risk",
    "cannibalization_risk_score",
    "cannibalization_risk_level",
    "cannibalization_recommended_action",
    "cannibalization_reasons",
    "cannibalization_matches",
)


def build_assignment_candidate_queries(assignment: TopicAssignment) -> list[str]:
    """Return deterministic candidate queries for overlap scoring."""
    metadata = assignment.metadata or {}
    queries: list[str] = []

    if assignment.topic_text:
        queries.append(assignment.topic_text.strip())

    raw_keywords = metadata.get("target_keywords")
    for query in _extract_keyword_strings(raw_keywords):
        cleaned = query.strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)

    return queries


def build_assignment_similarity_query(assignment: TopicAssignment) -> str:
    """Build enriched text for embedding-based cannibalization retrieval."""
    parts = [assignment.topic_text]
    meta = assignment.metadata or {}
    if meta.get("description"):
        parts.append(str(meta["description"]))
    keywords = meta.get("target_keywords")
    if keywords and isinstance(keywords, list):
        parts.append(", ".join(str(k) for k in keywords[:10]))
    return " | ".join(parts)


def build_assignment_assessments(
    assignments: list[TopicAssignment],
    query_texts: list[str],
    cannibal_results: dict[str, list[CannibalizationMatch]],
    *,
    signal_overrides_by_query: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build planner-ready assessments keyed by assignment id."""
    assessments: dict[str, dict[str, Any]] = {}
    for assignment, query_text in zip(assignments, query_texts):
        assessments[assignment.id] = assess_assignment_cannibalization(
            assignment,
            cannibal_results.get(query_text, []),
            match_signal_overrides=(signal_overrides_by_query or {}).get(query_text, {}),
        )
    return assessments


def assess_assignment_cannibalization(
    assignment: TopicAssignment,
    matches: list[CannibalizationMatch],
    *,
    match_signal_overrides: dict[str, dict[str, Any]] | None = None,
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
        (
            _score_match(
                assignment,
                match,
                signal_override=(match_signal_overrides or {}).get(match.inventory_id, {}),
            )
            for match in matches
        ),
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


async def persist_assignment_cannibalization_snapshots(
    session_factory: Any,
    *,
    company_id: _uuid.UUID,
    discovery_id: _uuid.UUID,
    assignments: list[TopicAssignment],
    source: str,
    matrix_version: int | None = None,
    parent_span: Any | None = None,
) -> int:
    """Persist already-computed assignment cannibalization metadata durably."""
    assessments = {
        assignment.id: _extract_persistable_metadata(assignment.metadata)
        for assignment in assignments
    }
    return await _persist_assignment_assessments(
        session_factory,
        company_id=company_id,
        discovery_id=discovery_id,
        assignments=assignments,
        assessments=assessments,
        source=source,
        matrix_version=matrix_version,
        parent_span=parent_span,
    )


async def recalculate_assignment_cannibalization_records(
    session_factory: Any,
    *,
    company_id: _uuid.UUID,
    discovery_id: _uuid.UUID,
    matrix_version: int | None = None,
    subdomain_node_id: _uuid.UUID | None = None,
    expansion_batch_id: _uuid.UUID | None = None,
    assignment_ids: list[_uuid.UUID] | None = None,
    source: str,
    parent_span: Any | None = None,
) -> int:
    """Recompute durable cannibalization evidence from persisted assignments."""
    from core.db.repositories.content_inventory_prompt_repo import (
        ContentInventoryPromptRepository,
        _compute_query_overlap_signals,
    )
    from core.db.repositories.content_inventory_repo import ContentInventoryRepository
    from core.db.repositories.topic_discovery_repo import TopicAssignmentRepository
    from core.services.content_inventory_service import ContentInventoryService

    sync_span = create_span(
        parent_span,
        "td-cannibalization/recalculate",
        metadata={
            "source": source,
            "embedding_model": settings.embedding_model,
            "company_id": str(company_id),
            "discovery_id": str(discovery_id),
        },
        input_data={
            "matrix_version": matrix_version,
            "subdomain_node_id": str(subdomain_node_id) if subdomain_node_id else None,
            "expansion_batch_id": str(expansion_batch_id) if expansion_batch_id else None,
            "assignment_count": len(assignment_ids or []),
        },
    )
    with scoped_bind(
        step_name="td_cannibalization_recalculate",
        discovery_id=str(discovery_id),
        company_id=str(company_id),
        source=source,
    ):
        async with session_factory() as session:
            assignment_repo = TopicAssignmentRepository(session)
            assignment_rows = await assignment_repo.list_for_cannibalization(
                discovery_id,
                matrix_version=matrix_version,
                subdomain_node_id=subdomain_node_id,
                expansion_batch_id=expansion_batch_id,
                assignment_ids=assignment_ids,
            )

        if not assignment_rows:
            end_span(sync_span, output={"count": 0})
            return 0

        assignments = [
            _db_row_to_pydantic_assignment(row)
            for row in assignment_rows
        ]
        query_texts = [
            build_assignment_similarity_query(assignment)
            for assignment in assignments
        ]

        async with session_factory() as session:
            ci_prompt_repo = ContentInventoryPromptRepository(session)
            cannibal_svc = ContentInventoryService(
                inventory_repo=ContentInventoryRepository(session),
            )
            cannibal_results = await cannibal_svc.check_cannibalization_batch(
                company_id,
                query_texts,
                threshold=settings.td_cannibalization_threshold,
                parent_span=sync_span,
                trace_name="td-cannibalization/batch-embed",
                trace_metadata={
                    "source": source,
                    "discovery_id": str(discovery_id),
                    "matrix_version": matrix_version,
                },
            )
            match_inventory_ids = {
                _uuid.UUID(match.inventory_id)
                for result_matches in cannibal_results.values()
                for match in result_matches
            }
            citation_lookup: dict[str, dict[str, Any]] = {}
            page_scope_lookup: dict[_uuid.UUID, dict[str, Any]] = {}
            if match_inventory_ids:
                end_dt = datetime.now(timezone.utc)
                start_dt = end_dt - timedelta(
                    days=settings.td_cannibalization_overlap_window_days,
                )
                citation_rows = await ci_prompt_repo.get_citation_metrics_batch(
                    company_id,
                    start_dt,
                    end_dt,
                    inventory_ids=list(match_inventory_ids),
                )
                citation_lookup = {
                    str(row["inventory_id"]): row
                    for row in citation_rows
                }
                page_scope_lookup = await ci_prompt_repo.get_page_prompt_scopes_batch(
                    list(match_inventory_ids)
                )

            signal_overrides_by_query: dict[str, dict[str, dict[str, Any]]] = {}
            for assignment, query_text in zip(assignments, query_texts):
                candidate_queries = build_assignment_candidate_queries(assignment)
                assignment_signal_overrides: dict[str, dict[str, Any]] = {}
                for match in cannibal_results.get(query_text, []):
                    inventory_uuid = _uuid.UUID(match.inventory_id)
                    query_overlap = _compute_query_overlap_signals(
                        page_scope_lookup.get(inventory_uuid, {
                            "root_prompt_ids": [],
                            "prompt_ids": [],
                            "fanout_prompt_ids": [],
                            "prompt_texts": [],
                        }),
                        candidate_queries,
                    )
                    citation_metrics = citation_lookup.get(match.inventory_id, {})
                    citation_count = int(citation_metrics.get("total_cited") or 0)
                    assignment_signal_overrides[match.inventory_id] = {
                        **query_overlap,
                        "citation_count": citation_count,
                        "citation_overlap_score": min(citation_count / 5, 1.0),
                    }
                signal_overrides_by_query[query_text] = assignment_signal_overrides

        assessments = build_assignment_assessments(
            assignments,
            query_texts,
            cannibal_results,
            signal_overrides_by_query=signal_overrides_by_query,
        )
        count = await _persist_assignment_assessments(
            session_factory,
            company_id=company_id,
            discovery_id=discovery_id,
            assignments=assignments,
            assessments=assessments,
            source=source,
            matrix_version=matrix_version,
            parent_span=sync_span,
        )
        end_span(sync_span, output={"count": count})
        return count


async def resolve_impacted_assignment_scope_for_inventory_changes(
    session_factory: Any,
    *,
    company_id: _uuid.UUID,
    inventory_ids: list[_uuid.UUID],
    assignment_cap: int | None = None,
) -> tuple[_uuid.UUID | None, list[_uuid.UUID]]:
    """Resolve a narrow assignment slice affected by page/prompt changes.

    Strategy:
    - Always include assignments whose durable top match points at the changed pages.
    - Also include a capped slice of planner-open assignments from the latest
      discovery so newly added pages can affect current planning work even when
      no durable top match exists yet.
    """
    from core.db.repositories.topic_discovery_repo import (
        TopicAssignmentCannibalizationRepository,
        TopicAssignmentRepository,
        TopicDiscoveryRepository,
    )

    inventory_id_list = list(dict.fromkeys(inventory_ids))
    if not inventory_id_list:
        return None, []

    effective_cap = assignment_cap or settings.td_cannibalization_delta_assignment_cap
    async with session_factory() as session:
        discovery_repo = TopicDiscoveryRepository(session)
        latest_discovery = await discovery_repo.get_latest_by_company(company_id)
        if latest_discovery is None:
            return None, []

        cannibal_repo = TopicAssignmentCannibalizationRepository(session)
        assignment_repo = TopicAssignmentRepository(session)

        affected_assignment_ids = await cannibal_repo.get_assignment_ids_by_top_match_inventory_ids(
            inventory_id_list,
            discovery_id=latest_discovery.id,
        )
        latest_planner_assignment_ids = await assignment_repo.list_delta_recompute_assignment_ids(
            latest_discovery.id,
            matrix_version=latest_discovery.matrix_version,
            limit=effective_cap,
        )

    ordered_assignment_ids: list[_uuid.UUID] = []
    for assignment_id in [*affected_assignment_ids, *latest_planner_assignment_ids]:
        if assignment_id not in ordered_assignment_ids:
            ordered_assignment_ids.append(assignment_id)

    logger.info(
        "td_cannibalization_delta_scope_resolved",
        company_id=str(company_id),
        discovery_id=str(latest_discovery.id),
        inventory_count=len(inventory_id_list),
        affected_count=len(affected_assignment_ids),
        planner_candidate_count=len(latest_planner_assignment_ids),
        assignment_count=len(ordered_assignment_ids),
    )
    return latest_discovery.id, ordered_assignment_ids


async def _persist_assignment_assessments(
    session_factory: Any,
    *,
    company_id: _uuid.UUID,
    discovery_id: _uuid.UUID,
    assignments: list[TopicAssignment],
    assessments: dict[str, dict[str, Any]],
    source: str,
    matrix_version: int | None = None,
    parent_span: Any | None = None,
) -> int:
    from core.db.repositories.topic_discovery_repo import (
        TopicAssignmentCannibalizationRepository,
        TopicAssignmentRepository,
    )

    persist_span = create_span(
        parent_span,
        "td-cannibalization/persist",
        metadata={
            "source": source,
            "company_id": str(company_id),
            "discovery_id": str(discovery_id),
        },
        input_data={"assignment_count": len(assignments)},
    )
    records = [
        _build_durable_record(
            assignment=assignment,
            company_id=company_id,
            discovery_id=discovery_id,
            assessment=assessments.get(assignment.id, {}),
            source=source,
            matrix_version=matrix_version,
        )
        for assignment in assignments
    ]
    metadata_by_assignment_id = {
        _uuid.UUID(assignment.id): assessments.get(assignment.id, {})
        for assignment in assignments
        if assignment.id in assessments
    }

    async with session_factory() as session:
        assignment_repo = TopicAssignmentRepository(session)
        cannibal_repo = TopicAssignmentCannibalizationRepository(session)
        await assignment_repo.bulk_merge_metadata(metadata_by_assignment_id)
        count = await cannibal_repo.bulk_upsert_assessments(records)
        await session.commit()

    logger.info(
        "td_cannibalization_persisted",
        source=source,
        discovery_id=str(discovery_id),
        company_id=str(company_id),
        count=count,
    )
    end_span(persist_span, output={"count": count})
    return count


def _build_durable_record(
    *,
    assignment: TopicAssignment,
    company_id: _uuid.UUID,
    discovery_id: _uuid.UUID,
    assessment: dict[str, Any],
    source: str,
    matrix_version: int | None,
) -> dict[str, Any]:
    top_match = (assessment.get("cannibalization_matches") or [None])[0]
    top_match_inventory_id = None
    if isinstance(top_match, dict) and top_match.get("inventory_id"):
        try:
            top_match_inventory_id = _uuid.UUID(str(top_match["inventory_id"]))
        except (TypeError, ValueError):
            top_match_inventory_id = None

    return {
        "assignment_id": _uuid.UUID(assignment.id),
        "discovery_id": discovery_id,
        "company_id": company_id,
        "top_match_inventory_id": top_match_inventory_id,
        "max_similarity": float(assessment.get("cannibalization_risk") or 0.0),
        "risk_score": float(assessment.get("cannibalization_risk_score") or 0.0),
        "risk_level": str(assessment.get("cannibalization_risk_level") or "none"),
        "recommended_action": str(
            assessment.get("cannibalization_recommended_action")
            or "safe_to_create_new"
        ),
        "reasons_json": list(assessment.get("cannibalization_reasons") or []),
        "matches_json": list(assessment.get("cannibalization_matches") or []),
        "signals_json": (
            (top_match or {}).get("signals")
            if isinstance(top_match, dict)
            else None
        ),
        "metadata_json": {
            "source": source,
            "matrix_version": matrix_version,
            "embedding_model": settings.embedding_model,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _extract_persistable_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {
            "cannibalization_risk": 0.0,
            "cannibalization_risk_score": 0.0,
            "cannibalization_risk_level": "none",
            "cannibalization_recommended_action": "safe_to_create_new",
            "cannibalization_reasons": [],
            "cannibalization_matches": [],
        }
    return {
        key: metadata.get(key)
        for key in _CANNIBALIZATION_METADATA_KEYS
    }


def _score_match(
    assignment: TopicAssignment,
    match: CannibalizationMatch,
    *,
    signal_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signal_override = signal_override or {}
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
    query_overlap = float(signal_override.get("query_overlap_score") or 0.0)
    citation_overlap = float(signal_override.get("citation_overlap_score") or 0.0)
    citation_count = int(signal_override.get("citation_count") or 0)
    matched_queries = [
        str(query)
        for query in (signal_override.get("matched_queries") or [])
        if query
    ]

    risk_score = min(
        1.0,
        (match.similarity * 0.58)
        + (lexical_overlap * 0.12)
        + (intent_overlap * 0.05)
        + (format_overlap * 0.03)
        + (query_overlap * 0.14)
        + (citation_overlap * 0.08),
    )
    if (
        match.similarity >= settings.td_cannibalization_high_risk_threshold
        and (
            lexical_overlap >= 0.1
            or intent_overlap >= 0.75
            or query_overlap >= 0.5
            or citation_overlap >= 0.3
        )
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
        "query_overlap": query_overlap,
        "citation_overlap": citation_overlap,
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
    if query_overlap >= 0.5 and matched_queries:
        reasons.append(
            f"Tracked query overlap is strong ({len(matched_queries)} matched query"
            f"{'ies' if len(matched_queries) != 1 else 'y'} in the page prompt scope)."
        )
    if citation_overlap >= 0.3 and citation_count > 0:
        reasons.append(
            f"The existing page is already cited in Daily Tracker responses ({citation_count} cited responses in scope)."
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
