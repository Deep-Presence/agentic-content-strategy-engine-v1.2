"""Content performance service — joins content inventory with GA4 traffic data.

Aggregates per-page traffic, AI referrals, velocity, source breakdown,
and lifecycle classification for the Content Performance dashboard.

This is a DB-only service (no JSON fallback) because both ``ga4_traffic_data``
and ``content_inventory`` live in PostgreSQL.
"""
from __future__ import annotations

import logging
import statistics
import uuid as _uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any, Sequence

from core.content_inventory.url_utils import extract_url_path, normalize_url
from core.db.repositories.analytics_repo import (
    AnalyticsConnectionRepository,
    GA4TrafficDataRepository,
)
from core.db.repositories.content_inventory_repo import ContentInventoryRepository

if TYPE_CHECKING:
    from core.db.repositories.content_inventory_prompt_repo import (
        ContentInventoryPromptRepository,
    )
    from core.db.repositories.gap_analysis_repo import GapAnalysisRepository

logger = logging.getLogger(__name__)

# ── Lifecycle thresholds ────────────────────────────────────────────

_STALE_VELOCITY_THRESHOLD = 2.0   # < 2 sessions/week
_STALE_FRESHNESS_DAYS = 180       # > 6 months since last update
_PEAKING_VELOCITY_MIN = 10.0      # high absolute traffic


# ── Structural score benchmarks ───────────────────────────────────
# Benchmarks derived from cited exemplar averages across gap analysis runs.
# Each signal has a weight (importance) and a benchmark (target value).
# Boolean signals: 1.0 if present (cited articles tend to have them).
# Numeric signals: score = min(1.0, value / benchmark).

_STRUCTURAL_SCORE_SIGNALS: list[dict[str, Any]] = [
    # Text Composition — 30 pts total
    {"field": "word_count", "weight": 10, "benchmark": 1800, "type": "numeric"},
    {"field": "sentence_count", "weight": 3, "benchmark": 100, "type": "numeric"},
    {"field": "paragraph_count", "weight": 3, "benchmark": 20, "type": "numeric"},
    {"field": "avg_paragraph_length", "weight": 2, "benchmark": 80, "type": "numeric"},
    {"field": "reading_level", "weight": 4, "benchmark": 10, "type": "numeric"},  # grade level ~10 is ideal
    {"field": "self_contained_ratio", "weight": 3, "benchmark": 0.8, "type": "numeric"},
    # Note: sentence_count, paragraph_count give diminishing returns past benchmark
    # Structural Elements — 25 pts total
    {"field": "h2_count", "weight": 6, "benchmark": 6, "type": "numeric"},
    {"field": "h3_count", "weight": 4, "benchmark": 4, "type": "numeric"},
    {"field": "list_block_count", "weight": 5, "benchmark": 3, "type": "numeric"},
    {"field": "table_count", "weight": 3, "benchmark": 1, "type": "numeric"},
    {"field": "ordered_list_count", "weight": 2, "benchmark": 1, "type": "numeric"},
    {"field": "code_block_count", "weight": 1, "benchmark": 1, "type": "numeric"},
    # h1_count intentionally excluded — most pages have exactly 1
    # Content Patterns — 30 pts total (boolean: present = full weight)
    {"field": "has_faq_section", "weight": 5, "type": "boolean"},
    {"field": "has_definition_opening", "weight": 4, "type": "boolean"},
    {"field": "has_key_takeaways", "weight": 5, "type": "boolean"},
    {"field": "has_comparison_table", "weight": 3, "type": "boolean"},
    {"field": "has_step_by_step", "weight": 4, "type": "boolean"},
    {"field": "has_research_refs", "weight": 5, "type": "boolean"},
    {"field": "has_expert_quotes", "weight": 4, "type": "boolean"},
    # Factual Density — 15 pts total
    {"field": "data_point_count", "weight": 6, "benchmark": 8, "type": "numeric"},
    {"field": "citation_density", "weight": 5, "benchmark": 0.005, "type": "numeric"},
    {"field": "named_entity_density", "weight": 4, "benchmark": 0.02, "type": "numeric"},
]

# Total possible weight (should sum to 100)
_TOTAL_WEIGHT = sum(s["weight"] for s in _STRUCTURAL_SCORE_SIGNALS)


def compute_structural_score(signals: dict[str, Any] | None) -> int:
    """Compute a 0-100 composite structural score from a page's signals JSONB.

    Scoring:
    - Boolean signals: full weight if True, 0 if False/missing.
    - Numeric signals: ``min(1.0, value / benchmark) * weight``.
      Values above benchmark get full marks (no penalty for exceeding).
    - Missing/None signals: score 0 for that signal.

    Returns an integer 0-100.
    """
    if not signals:
        return 0

    score = 0.0
    for sig in _STRUCTURAL_SCORE_SIGNALS:
        field = sig["field"]
        weight = sig["weight"]
        raw = signals.get(field)

        if raw is None:
            continue

        if sig["type"] == "boolean":
            if raw is True or raw == 1:
                score += weight
        else:
            benchmark = sig["benchmark"]
            try:
                val = float(raw)
            except (ValueError, TypeError):
                continue
            if benchmark > 0:
                score += min(1.0, val / benchmark) * weight

    # Normalize to 0-100
    normalized = round(score / _TOTAL_WEIGHT * 100) if _TOTAL_WEIGHT > 0 else 0
    return max(0, min(100, normalized))


def _compute_freshness_assessment(
    item: Any,
    exemplar_dates: Sequence[datetime] | None = None,
) -> dict[str, Any]:
    """Return a backend-owned freshness payload for a single inventory item.

    Uses observed page dates plus cited exemplar dates when available.
    """
    today = date.today()
    published_at = getattr(item, "published_at", None)
    modified_at = getattr(item, "content_modified_at", None)

    content_age_days = None
    if published_at is not None:
        content_age_days = (today - published_at.date()).days

    reference_dt = modified_at or published_at
    last_updated_age_days = None
    if reference_dt is not None:
        last_updated_age_days = (today - reference_dt.date()).days

    exemplar_age_days = [
        max((today - dt.date()).days, 0)
        for dt in (exemplar_dates or [])
        if dt is not None
    ]
    benchmark_sample_size = len(exemplar_age_days)
    avg_age = None
    median_age = None
    freshness_delta_days = None
    freshness_score = None
    freshness_status = "insufficient_data"

    if benchmark_sample_size > 0:
        avg_age = round(sum(exemplar_age_days) / benchmark_sample_size)
        median_age = round(statistics.median(exemplar_age_days))

    if last_updated_age_days is None:
        reason = (
            "Published and modified dates are unavailable, so freshness cannot "
            "be benchmarked yet."
        )
    elif benchmark_sample_size == 0 or median_age is None:
        if last_updated_age_days <= 30:
            freshness_status = "heuristic_fresh"
            freshness_score = 90
        elif last_updated_age_days <= 90:
            freshness_status = "heuristic_recent"
            freshness_score = 75
        elif last_updated_age_days <= 180:
            freshness_status = "heuristic_stale"
            freshness_score = 55
        else:
            freshness_status = "heuristic_old"
            freshness_score = 30
        reason = (
            "Cited exemplar freshness benchmark is not available yet, so this "
            "uses a simple age-based heuristic from the page's last updated age."
        )
    else:
        freshness_delta_days = last_updated_age_days - median_age
        if freshness_delta_days <= -30:
            freshness_status = "fresher_than_benchmark"
            freshness_score = 95
        elif abs(freshness_delta_days) <= 30:
            freshness_status = "within_range"
            freshness_score = 80
        elif freshness_delta_days <= 90:
            freshness_status = "slightly_stale"
            freshness_score = 60
        else:
            freshness_status = "stale"
            freshness_score = 35
        reason = (
            f"Freshness benchmark: last updated age is {last_updated_age_days} "
            f"days versus a cited exemplar median of {median_age} days across "
            f"{benchmark_sample_size} exemplars."
        )

    return {
        "content_age_days": content_age_days,
        "last_updated_age_days": last_updated_age_days,
        "cited_exemplar_avg_age_days": avg_age,
        "cited_exemplar_median_age_days": median_age,
        "benchmark_sample_size": benchmark_sample_size,
        "freshness_delta_days": freshness_delta_days,
        "freshness_score": freshness_score,
        "freshness_status": freshness_status,
        "freshness_reason": reason,
    }


# ── Helpers ─────────────────────────────────────────────────────────


def _compute_velocity_trend(
    current_velocity: float, previous_velocity: float,
) -> tuple[str, float]:
    """Return (trend, pct_change) comparing current vs previous velocity."""
    if previous_velocity == 0:
        if current_velocity > 0:
            return "up", 1.0
        return "flat", 0.0
    pct_change = (current_velocity - previous_velocity) / previous_velocity
    if pct_change > 0.10:
        return "up", pct_change
    if pct_change < -0.10:
        return "down", pct_change
    return "flat", pct_change


def _classify_lifecycle(
    velocity: float, pct_change: float, freshness_days: int,
) -> str:
    """Classify content lifecycle stage from velocity + freshness signals."""
    if velocity < _STALE_VELOCITY_THRESHOLD and freshness_days > _STALE_FRESHNESS_DAYS:
        return "stale"
    if pct_change > 0.20:
        return "growing"
    if pct_change < -0.20:
        return "declining"
    if velocity > _PEAKING_VELOCITY_MIN and 0 <= pct_change <= 0.10:
        return "peaking"
    return "stable"


_SOCIAL_DOMAINS = frozenset({
    "facebook", "twitter", "linkedin", "instagram", "pinterest",
    "reddit", "youtube", "tiktok", "t.co", "x.com",
})


def _classify_channel(
    source: str, medium: str, is_ai_referral: bool,
) -> str:
    """Classify a (source, medium) pair into a traffic channel."""
    if is_ai_referral:
        return "ai_referral"
    medium_lower = medium.lower() if medium else ""
    source_lower = source.lower() if source else ""
    if medium_lower == "organic":
        return "organic"
    if source_lower == "(direct)" or medium_lower == "(none)":
        return "direct"
    if medium_lower == "social" or any(d in source_lower for d in _SOCIAL_DOMAINS):
        return "social"
    if medium_lower == "referral":
        return "referral"
    if medium_lower == "cpc":
        return "paid"
    return "other"


def _canonicalize_path(value: str) -> str:
    """Normalize a URL or path into the comparable path form used for joins."""
    return extract_url_path(value or "").lower().rstrip("/") or "/"


def _build_path_to_traffic(
    rows: Sequence[Any],
) -> dict[str, dict[str, int]]:
    """Build {page_path: {total_sessions, total_pageviews, ai_sessions}} lookup.

    ``landing_page_url`` is the legacy storage field name, but for Content
    Performance traffic syncs it now contains GA4 ``pagePath`` values.
    We lowercase + strip trailing slash to match extract_url_path output.
    """
    lookup: dict[str, dict[str, int]] = {}
    for row in rows:
        path = row.landing_page_url
        if not path or path == "(not set)":
            continue
        path = _canonicalize_path(path)
        existing = lookup.get(path)
        if existing:
            existing["total_sessions"] += int(row.total_sessions or 0)
            existing["total_pageviews"] += int(row.total_pageviews or 0)
            existing["ai_sessions"] += int(row.ai_sessions or 0)
        else:
            lookup[path] = {
                "total_sessions": int(row.total_sessions or 0),
                "total_pageviews": int(row.total_pageviews or 0),
                "ai_sessions": int(row.ai_sessions or 0),
            }
    return lookup


def _candidate_inventory_urls(item: Any) -> tuple[str, str | None]:
    """Return exact and normalized inventory URLs for downstream matching."""
    raw_url = (getattr(item, "url", None) or "").strip()
    normalized_url = (getattr(item, "url_normalized", None) or "").strip()
    if not normalized_url and raw_url:
        normalized_url = normalize_url(raw_url)
    return raw_url, normalized_url or None


# ── Service ─────────────────────────────────────────────────────────


class ContentPerformanceService:
    """Joins content inventory with GA4 traffic data for per-page analytics."""

    def __init__(
        self,
        *,
        traffic_repo: GA4TrafficDataRepository,
        inventory_repo: ContentInventoryRepository,
        connection_repo: AnalyticsConnectionRepository | None = None,
        ci_prompt_repo: "ContentInventoryPromptRepository | None" = None,
        gap_repo: "GapAnalysisRepository | None" = None,
    ) -> None:
        self._traffic = traffic_repo
        self._inventory = inventory_repo
        self._connections = connection_repo
        self._ci_prompt = ci_prompt_repo
        self._gap = gap_repo

    async def get_readiness(
        self,
        company_id: _uuid.UUID,
        *,
        tenant_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Return readiness metadata for the Content Performance analytics chain."""
        items, total_inventory = await self._inventory.get_by_company(
            company_id, limit=1000, offset=0,
        )
        inventory_paths = {
            _canonicalize_path(item.url_normalized or item.url or "")
            for item in items
        }
        inventory_paths_sample = sorted(inventory_paths)[:5]

        connection = None
        if self._connections is not None:
            connection = await self._connections.get_active_connection(
                company_id, tenant_id,
            )

        if connection is None:
            return {
                "state": "not_connected",
                "message": (
                    "Connect Google Analytics 4 in Settings to load page traffic "
                    "and AI referral data."
                ),
                "connection_active": False,
                "has_selected_property": False,
                "inventory_pages": int(total_inventory),
            }

        if not connection.ga4_property_id:
            return {
                "state": "property_required",
                "message": (
                    "Select a GA4 property in Settings to start syncing "
                    "analytics data."
                ),
                "connection_active": True,
                "has_selected_property": False,
                "last_sync_at": connection.last_sync_at,
                "last_sync_status": (
                    connection.last_sync_status.value
                    if connection.last_sync_status else ""
                ),
                "last_sync_error": connection.last_sync_error or "",
                "inventory_pages": int(total_inventory),
            }

        ga4_rows_total = await self._traffic.count_rows(company_id)
        ga4_rows_in_window = await self._traffic.count_rows(
            company_id, start_date=start_date, end_date=end_date,
        )
        ga4_paths_total = {
            _canonicalize_path(path)
            for path in await self._traffic.list_distinct_landing_page_urls(company_id)
        }
        ga4_paths_window = {
            _canonicalize_path(path)
            for path in await self._traffic.list_distinct_landing_page_urls(
                company_id, start_date=start_date, end_date=end_date,
            )
        }
        matched_total = len(inventory_paths & ga4_paths_total)
        matched_window = len(inventory_paths & ga4_paths_window)
        unmatched_total = len(ga4_paths_total - inventory_paths)
        unmatched_window = len(ga4_paths_window - inventory_paths)
        window_aggregates = await self._traffic.get_per_page_aggregates(
            company_id, start_date, end_date,
        )
        unmatched_window_sessions: dict[str, int] = {}
        for row in window_aggregates:
            path = _canonicalize_path(str(row.landing_page_url or ""))
            if path in inventory_paths:
                continue
            unmatched_window_sessions[path] = (
                unmatched_window_sessions.get(path, 0)
                + int(row.total_sessions or 0)
            )
        unmatched_ga4_paths_sample = [
            {"path": path, "sessions": sessions}
            for path, sessions in sorted(
                unmatched_window_sessions.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ]
        if not unmatched_ga4_paths_sample and unmatched_window > 0:
            unmatched_ga4_paths_sample = [
                {"path": path, "sessions": 0}
                for path in sorted(ga4_paths_window - inventory_paths)[:5]
            ]

        state = "ready"
        message = "GA4 analytics is ready for Content Performance."

        if connection.last_sync_status and connection.last_sync_status.value == "failed":
            state = "sync_failed"
            message = (
                "The last GA4 sync failed. Fix the integration error in Settings "
                "and run sync again."
            )
        elif connection.last_sync_at is None and ga4_rows_total == 0:
            state = "never_synced"
            message = (
                "GA4 is connected and a property is selected, but the initial "
                "sync has not completed yet."
            )
        elif ga4_rows_total == 0:
            state = "no_data"
            message = (
                "GA4 is connected, but no traffic rows have been synced yet."
            )
        elif total_inventory > 0 and matched_total == 0:
            state = "no_matching_pages"
            message = (
                "GA4 data exists, but none of the synced GA4 page paths match "
                "your content inventory URLs yet."
            )
        elif ga4_rows_in_window == 0 or matched_window == 0:
            state = "no_recent_data"
            message = (
                "GA4 is connected, but there is no matched page traffic in the "
                "current reporting window."
            )

        return {
            "state": state,
            "message": message,
            "connection_active": True,
            "has_selected_property": True,
            "last_sync_at": connection.last_sync_at,
            "last_sync_status": (
                connection.last_sync_status.value
                if connection.last_sync_status else ""
            ),
            "last_sync_error": connection.last_sync_error or "",
            "inventory_pages": int(total_inventory),
            "ga4_rows_total": int(ga4_rows_total),
            "ga4_rows_in_window": int(ga4_rows_in_window),
            "matched_inventory_pages": int(matched_total),
            "matched_inventory_pages_in_window": int(matched_window),
            "unmatched_ga4_paths_total": int(unmatched_total),
            "unmatched_ga4_paths_in_window": int(unmatched_window),
            "inventory_paths_sample": inventory_paths_sample,
            "unmatched_ga4_paths_sample": unmatched_ga4_paths_sample,
        }

    async def get_content_table(
        self,
        company_id: _uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Return per-content-piece traffic summary for the content table.

        Joins content_inventory rows with GA4 per-page aggregates.
        Computes velocity, velocity_trend, freshness_days, and lifecycle.
        """
        # Fetch inventory (all pages, no pagination limit for dashboard)
        items, _total = await self._inventory.get_by_company(
            company_id, limit=1000, offset=0,
        )
        if not items:
            return []

        period_days = (end_date - start_date).days + 1
        period_weeks = max(period_days / 7.0, 1.0)

        # Current period aggregates
        current_rows = await self._traffic.get_per_page_aggregates(
            company_id, start_date, end_date,
        )
        current_lookup = _build_path_to_traffic(current_rows)

        # Previous period aggregates (same length, immediately before)
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        prev_rows = await self._traffic.get_per_page_aggregates(
            company_id, prev_start, prev_end,
        )
        prev_lookup = _build_path_to_traffic(prev_rows)

        # ── Citation metrics (Gaps 1+2) ──────────────────────────
        citation_lookup: dict[str, dict[str, Any]] = {}
        if self._ci_prompt is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
            cit_rows = await self._ci_prompt.get_citation_metrics_batch(
                company_id, start_dt, end_dt,
            )
            citation_lookup = {str(r["inventory_id"]): r for r in cit_rows}

        # ── Queries covered (Gap 3) ──────────────────────────────
        url_to_queries: dict[str, int] = {}
        if self._gap is not None:
            pub_url_counts = await self._gap.count_queries_targeting_inventory_batch(
                company_id,
            )
            for pub_url, cnt in pub_url_counts.items():
                norm = normalize_url(pub_url) if pub_url else ""
                if norm:
                    url_to_queries[norm] = url_to_queries.get(norm, 0) + cnt

        today = date.today()
        results: list[dict[str, Any]] = []

        for item in items:
            path = extract_url_path(item.url_normalized or item.url or "")
            current = current_lookup.get(path, {})
            previous = prev_lookup.get(path, {})

            traffic = current.get("total_sessions", 0)
            ai_referrals = current.get("ai_sessions", 0)
            velocity = traffic / period_weeks

            prev_traffic = previous.get("total_sessions", 0)
            prev_velocity = prev_traffic / period_weeks

            trend, pct_change = _compute_velocity_trend(velocity, prev_velocity)

            freshness_days = 0
            if item.content_modified_at:
                freshness_days = (today - item.content_modified_at.date()).days
            elif item.published_at:
                freshness_days = (today - item.published_at.date()).days

            lifecycle = _classify_lifecycle(velocity, pct_change, freshness_days)

            results.append({
                "inventory_id": str(item.id),
                "url": item.url or "",
                "title": item.title or "",
                "traffic": traffic,
                "ai_referrals": ai_referrals,
                "velocity": round(velocity, 2),
                "velocity_trend": trend,
                "freshness_days": freshness_days,
                "lifecycle": lifecycle,
                "content_type": item.content_type_detected or "",
                "word_count": item.word_count or 0,
                "published_at": (
                    item.published_at.isoformat() if item.published_at else None
                ),
                "structural_score": compute_structural_score(
                    item.structural_signals,
                ),
            })

            # ── Enrich with citation / platform / queries data ───
            cit = citation_lookup.get(str(item.id), {})
            results[-1]["citations"] = cit.get("total_cited", 0)
            results[-1]["platforms"] = {
                "chatgpt": bool(cit.get("cited_openai", False)),
                "claude": bool(cit.get("cited_claude", False)),
                "gemini": bool(cit.get("cited_gemini", False)),
                "perplexity": bool(cit.get("cited_perplexity", False)),
                "google_ai": bool(cit.get("cited_gemini", False)),
            }
            inv_norm = item.url_normalized or normalize_url(item.url or "")
            results[-1]["queries_covered"] = url_to_queries.get(inv_norm, 0)

        # Sort by traffic descending
        results.sort(key=lambda r: r["traffic"], reverse=True)
        return results

    async def get_content_detail(
        self,
        company_id: _uuid.UUID,
        inventory_id: _uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any] | None:
        """Return detailed analytics for a single content piece.

        Includes daily timeseries, source breakdown, and AI platform breakdown.
        Returns None if the inventory item doesn't exist or doesn't belong
        to the company.
        """
        item = await self._inventory.get_by_id(inventory_id)
        if item is None or item.company_id != company_id:
            return None

        path = extract_url_path(item.url_normalized or item.url or "")

        period_days = (end_date - start_date).days + 1
        period_weeks = max(period_days / 7.0, 1.0)

        # Fetch timeseries + source breakdown + AI platform breakdown
        timeseries = await self._traffic.get_daily_timeseries(
            company_id, path, start_date, end_date,
        )
        sources = await self._traffic.get_source_breakdown(
            company_id, path, start_date, end_date,
        )
        ai_platforms = await self._traffic.get_ai_platform_breakdown(
            company_id, path, start_date, end_date,
        )

        # Previous period for velocity trend
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        prev_timeseries = await self._traffic.get_daily_timeseries(
            company_id, path, prev_start, prev_end,
        )

        # Aggregate current and previous totals
        total_sessions = sum(int(r.sessions or 0) for r in timeseries)
        total_ai = sum(int(r.ai_sessions or 0) for r in timeseries)
        prev_sessions = sum(int(r.sessions or 0) for r in prev_timeseries)

        velocity = total_sessions / period_weeks
        prev_velocity = prev_sessions / period_weeks
        trend, pct_change = _compute_velocity_trend(velocity, prev_velocity)

        today = date.today()
        freshness_days = 0
        if item.content_modified_at:
            freshness_days = (today - item.content_modified_at.date()).days
        elif item.published_at:
            freshness_days = (today - item.published_at.date()).days

        lifecycle = _classify_lifecycle(velocity, pct_change, freshness_days)
        exemplar_dates: list[datetime] = []
        if self._gap is not None:
            raw_url, normalized_url = _candidate_inventory_urls(item)
            exemplar_dates = await self._gap.get_cited_exemplar_dates_for_inventory_url(
                company_id,
                raw_url,
                normalized_url=normalized_url,
            )
        freshness = _compute_freshness_assessment(item, exemplar_dates)

        # Daily traffic points
        daily_traffic = [
            {
                "date": r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date),
                "sessions": int(r.sessions or 0),
                "pageviews": int(r.pageviews or 0),
                "ai_sessions": int(r.ai_sessions or 0),
            }
            for r in timeseries
        ]

        # Source breakdown — classify into channels
        channel_sessions: dict[str, int] = {}
        for r in sources:
            channel = _classify_channel(
                r.source or "", r.medium or "", bool(r.is_ai_referral),
            )
            channel_sessions[channel] = (
                channel_sessions.get(channel, 0) + int(r.sessions or 0)
            )

        source_total = sum(channel_sessions.values()) or 1
        source_breakdown = [
            {
                "channel": ch,
                "sessions": sess,
                "percentage": round(sess / source_total * 100, 1),
            }
            for ch, sess in sorted(
                channel_sessions.items(), key=lambda x: x[1], reverse=True,
            )
        ]

        # AI platform breakdown
        ai_platform_breakdown = [
            {
                "platform": r.ai_platform or "unknown",
                "sessions": int(r.sessions or 0),
            }
            for r in ai_platforms
            if r.ai_platform
        ]

        # ── Citation timeline (Gap 4) + per-page metrics (Gaps 1+2) ──
        citation_timeline: list[dict[str, Any]] = []
        total_cited = 0
        platforms: dict[str, bool] = {
            "chatgpt": False, "claude": False, "gemini": False,
            "perplexity": False, "google_ai": False,
        }
        if self._ci_prompt is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
            timeline_rows = await self._ci_prompt.get_citation_timeline(
                inventory_id, start_dt, end_dt,
            )
            citation_timeline = [
                {
                    "date": r["day"].isoformat() if hasattr(r["day"], "isoformat") else str(r["day"]),
                    "cited": r["cited"],
                    "total_responses": r["total_responses"],
                }
                for r in timeline_rows
            ]
            total_cited = sum(r["cited"] for r in timeline_rows)
            # Per-engine platforms
            cit_batch = await self._ci_prompt.get_citation_metrics_batch(
                company_id, start_dt, end_dt,
            )
            cit_data = {str(r["inventory_id"]): r for r in cit_batch}.get(
                str(inventory_id), {},
            )
            platforms = {
                "chatgpt": bool(cit_data.get("cited_openai", False)),
                "claude": bool(cit_data.get("cited_claude", False)),
                "gemini": bool(cit_data.get("cited_gemini", False)),
                "perplexity": bool(cit_data.get("cited_perplexity", False)),
                "google_ai": bool(cit_data.get("cited_gemini", False)),
            }

        # ── Queries covered (Gap 3) ──────────────────────────────
        queries_covered = 0
        if self._gap is not None:
            pub_url_counts = await self._gap.count_queries_targeting_inventory_batch(
                company_id,
            )
            inv_norm = item.url_normalized or normalize_url(item.url or "")
            for pub_url, cnt in pub_url_counts.items():
                if normalize_url(pub_url) == inv_norm:
                    queries_covered += cnt

        return {
            "inventory_id": str(item.id),
            "url": item.url or "",
            "title": item.title or "",
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "traffic": total_sessions,
            "ai_referrals": total_ai,
            "velocity": round(velocity, 2),
            "velocity_trend": trend,
            "freshness_days": freshness_days,
            "lifecycle": lifecycle,
            "daily_traffic": daily_traffic,
            "source_breakdown": source_breakdown,
            "ai_platform_breakdown": ai_platform_breakdown,
            "structural_signals": item.structural_signals,
            "structural_score": compute_structural_score(
                item.structural_signals,
            ),
            "citation_timeline": citation_timeline,
            "citations": total_cited,
            "freshness": freshness,
            "platforms": platforms,
            "queries_covered": queries_covered,
        }

    async def get_velocity_insights(
        self,
        company_id: _uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Return velocity + lifecycle insights for all content pieces.

        Uses the same data as get_content_table but returns a subset of
        fields focused on velocity and lifecycle.
        """
        table = await self.get_content_table(company_id, start_date, end_date)
        return [
            {
                "inventory_id": row["inventory_id"],
                "url": row["url"],
                "title": row["title"],
                "velocity": row["velocity"],
                "velocity_trend": row["velocity_trend"],
                "lifecycle": row["lifecycle"],
                "traffic": row["traffic"],
            }
            for row in table
        ]
