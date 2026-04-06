"""Tests for ContentPerformanceService.

Service is tested with mocked repositories — no DB needed.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.content_inventory.url_utils import extract_url_path
from core.services.content_performance_service import (
    ContentPerformanceService,
    _classify_channel,
    _classify_lifecycle,
    _compute_velocity_trend,
)


# ── extract_url_path tests ──────────────────────────────────────────


class TestExtractUrlPath:
    """Tests for the URL path extraction utility."""

    def test_full_url(self):
        assert extract_url_path("https://example.com/blog/post") == "/blog/post"

    def test_full_url_with_trailing_slash(self):
        assert extract_url_path("https://example.com/blog/post/") == "/blog/post"

    def test_root_url(self):
        assert extract_url_path("https://example.com/") == "/"

    def test_root_url_no_slash(self):
        assert extract_url_path("https://example.com") == "/"

    def test_path_only(self):
        assert extract_url_path("/already-a-path") == "/already-a-path"

    def test_path_with_trailing_slash(self):
        assert extract_url_path("/path/") == "/path"

    def test_case_insensitive(self):
        assert extract_url_path("https://Example.com/Blog/Post") == "/blog/post"

    def test_empty_string(self):
        assert extract_url_path("") == "/"

    def test_whitespace(self):
        assert extract_url_path("   ") == "/"

    def test_url_with_query_params(self):
        # urlparse keeps query in separate field; path component has no query
        assert extract_url_path("https://example.com/page?utm=123") == "/page"

    def test_url_with_fragment(self):
        assert extract_url_path("https://example.com/page#section") == "/page"


# ── Velocity trend tests ────────────────────────────────────────────


class TestComputeVelocityTrend:
    """Tests for velocity trend computation."""

    def test_up_trend(self):
        trend, pct = _compute_velocity_trend(20.0, 10.0)
        assert trend == "up"
        assert pct == pytest.approx(1.0)

    def test_down_trend(self):
        trend, pct = _compute_velocity_trend(8.0, 10.0)
        assert trend == "down"
        assert pct == pytest.approx(-0.2)

    def test_flat_trend(self):
        trend, pct = _compute_velocity_trend(10.5, 10.0)
        assert trend == "flat"
        assert pct == pytest.approx(0.05)

    def test_zero_previous_with_current(self):
        trend, pct = _compute_velocity_trend(5.0, 0.0)
        assert trend == "up"
        assert pct == 1.0

    def test_zero_both(self):
        trend, pct = _compute_velocity_trend(0.0, 0.0)
        assert trend == "flat"
        assert pct == 0.0


# ── Lifecycle classification tests ──────────────────────────────────


class TestClassifyLifecycle:
    """Tests for lifecycle stage classification."""

    def test_growing(self):
        assert _classify_lifecycle(15.0, 0.30, 30) == "growing"

    def test_declining(self):
        assert _classify_lifecycle(15.0, -0.30, 30) == "declining"

    def test_stale(self):
        assert _classify_lifecycle(1.0, -0.05, 200) == "stale"

    def test_peaking(self):
        assert _classify_lifecycle(15.0, 0.05, 30) == "peaking"

    def test_stable(self):
        assert _classify_lifecycle(5.0, 0.0, 30) == "stable"

    def test_stale_requires_both_conditions(self):
        # Low velocity but recent content → not stale
        assert _classify_lifecycle(1.0, 0.0, 30) != "stale"
        # Old content but high velocity → not stale
        assert _classify_lifecycle(10.0, 0.0, 200) != "stale"


# ── Channel classification tests ────────────────────────────────────


class TestClassifyChannel:
    """Tests for traffic source channel classification."""

    def test_ai_referral(self):
        assert _classify_channel("chatgpt.com", "referral", True) == "ai_referral"

    def test_organic(self):
        assert _classify_channel("google", "organic", False) == "organic"

    def test_direct(self):
        assert _classify_channel("(direct)", "(none)", False) == "direct"

    def test_social(self):
        assert _classify_channel("twitter", "social", False) == "social"

    def test_social_by_domain(self):
        assert _classify_channel("linkedin.com", "referral", False) == "social"

    def test_referral(self):
        assert _classify_channel("somesite.com", "referral", False) == "referral"

    def test_paid(self):
        assert _classify_channel("google", "cpc", False) == "paid"

    def test_other(self):
        assert _classify_channel("email-tool", "email", False) == "other"


# ── Helpers ─────────────────────────────────────────────────────────


def _make_traffic_row(
    landing_page_url: str = "/blog/post",
    total_sessions: int = 100,
    total_pageviews: int = 150,
    ai_sessions: int = 10,
):
    """Create a mock per-page aggregate row."""
    return SimpleNamespace(
        landing_page_url=landing_page_url,
        total_sessions=total_sessions,
        total_pageviews=total_pageviews,
        ai_sessions=ai_sessions,
    )


def _make_inventory_item(
    url: str = "https://example.com/blog/post",
    title: str = "Test Post",
    company_id: uuid.UUID | None = None,
    content_modified_at: datetime | None = None,
    published_at: datetime | None = None,
    word_count: int = 1200,
):
    """Create a mock ContentInventoryModel."""
    m = MagicMock()
    m.id = uuid.uuid4()
    m.url = url
    m.url_normalized = url.lower()
    m.title = title
    m.company_id = company_id or uuid.uuid4()
    m.content_modified_at = content_modified_at
    m.published_at = published_at or datetime.now(timezone.utc)
    m.word_count = word_count
    m.content_type_detected = "blog_post"
    return m


def _make_timeseries_row(
    d: date, sessions: int = 10, pageviews: int = 15, ai_sessions: int = 1,
):
    return SimpleNamespace(
        date=d, sessions=sessions, pageviews=pageviews, ai_sessions=ai_sessions,
    )


def _make_source_row(
    source: str = "google",
    medium: str = "organic",
    is_ai_referral: bool = False,
    ai_platform: str = "",
    sessions: int = 50,
):
    return SimpleNamespace(
        source=source, medium=medium,
        is_ai_referral=is_ai_referral, ai_platform=ai_platform,
        sessions=sessions,
    )


def _make_platform_row(platform: str = "openai", sessions: int = 5):
    return SimpleNamespace(ai_platform=platform, sessions=sessions)


# ── Service tests ───────────────────────────────────────────────────


@pytest.fixture
def traffic_repo():
    repo = AsyncMock()
    repo.get_per_page_aggregates = AsyncMock(return_value=[])
    repo.get_daily_timeseries = AsyncMock(return_value=[])
    repo.get_source_breakdown = AsyncMock(return_value=[])
    repo.get_ai_platform_breakdown = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def inventory_repo():
    repo = AsyncMock()
    repo.get_by_company = AsyncMock(return_value=([], 0))
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def service(traffic_repo, inventory_repo):
    return ContentPerformanceService(
        traffic_repo=traffic_repo,
        inventory_repo=inventory_repo,
    )


class TestGetContentTable:
    """Tests for get_content_table()."""

    @pytest.mark.asyncio
    async def test_empty_inventory(self, service, inventory_repo):
        inventory_repo.get_by_company.return_value = ([], 0)
        result = await service.get_content_table(
            uuid.uuid4(), date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_inventory_no_traffic(self, service, inventory_repo):
        cid = uuid.uuid4()
        items = [_make_inventory_item(company_id=cid)]
        inventory_repo.get_by_company.return_value = (items, 1)

        result = await service.get_content_table(
            cid, date(2026, 3, 1), date(2026, 3, 28),
        )
        assert len(result) == 1
        assert result[0]["traffic"] == 0
        assert result[0]["velocity"] == 0.0
        assert result[0]["velocity_trend"] == "flat"

    @pytest.mark.asyncio
    async def test_url_matching(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        items = [
            _make_inventory_item(
                url="https://example.com/Blog/Post",
                company_id=cid,
            ),
        ]
        inventory_repo.get_by_company.return_value = (items, 1)
        traffic_repo.get_per_page_aggregates.return_value = [
            _make_traffic_row(
                landing_page_url="/blog/post",
                total_sessions=100,
                ai_sessions=10,
            ),
        ]

        result = await service.get_content_table(
            cid, date(2026, 3, 1), date(2026, 3, 28),
        )
        assert len(result) == 1
        assert result[0]["traffic"] == 100
        assert result[0]["ai_referrals"] == 10

    @pytest.mark.asyncio
    async def test_velocity_computation(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        items = [_make_inventory_item(company_id=cid)]
        inventory_repo.get_by_company.return_value = (items, 1)

        # 28-day period → 4 weeks → velocity = 280 / 4 = 70
        traffic_repo.get_per_page_aggregates.return_value = [
            _make_traffic_row(
                landing_page_url="/blog/post",
                total_sessions=280,
            ),
        ]

        result = await service.get_content_table(
            cid, date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result[0]["velocity"] == 70.0

    @pytest.mark.asyncio
    async def test_velocity_trend_up(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        items = [_make_inventory_item(company_id=cid)]
        inventory_repo.get_by_company.return_value = (items, 1)

        # Current period: 200 sessions; previous period: 100 sessions
        # → 100% increase → "up"
        call_count = 0

        async def mock_aggregates(company_id, start, end):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # current period
                return [_make_traffic_row("/blog/post", total_sessions=200)]
            return [_make_traffic_row("/blog/post", total_sessions=100)]

        traffic_repo.get_per_page_aggregates = mock_aggregates

        result = await service.get_content_table(
            cid, date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result[0]["velocity_trend"] == "up"

    @pytest.mark.asyncio
    async def test_sorted_by_traffic_desc(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        items = [
            _make_inventory_item(url="https://example.com/low", company_id=cid),
            _make_inventory_item(url="https://example.com/high", company_id=cid),
        ]
        inventory_repo.get_by_company.return_value = (items, 2)
        traffic_repo.get_per_page_aggregates.return_value = [
            _make_traffic_row("/low", total_sessions=10),
            _make_traffic_row("/high", total_sessions=500),
        ]

        result = await service.get_content_table(
            cid, date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result[0]["url"] == "https://example.com/high"
        assert result[1]["url"] == "https://example.com/low"


class TestGetContentDetail:
    """Tests for get_content_detail()."""

    @pytest.mark.asyncio
    async def test_not_found(self, service, inventory_repo):
        inventory_repo.get_by_id.return_value = None
        result = await service.get_content_detail(
            uuid.uuid4(), uuid.uuid4(),
            date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_company(self, service, inventory_repo):
        item = _make_inventory_item(company_id=uuid.uuid4())
        inventory_repo.get_by_id.return_value = item
        result = await service.get_content_detail(
            uuid.uuid4(),  # different company
            item.id,
            date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_happy_path(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        item = _make_inventory_item(company_id=cid)
        inventory_repo.get_by_id.return_value = item

        today = date.today()
        traffic_repo.get_daily_timeseries.return_value = [
            _make_timeseries_row(today - timedelta(days=1), sessions=50, ai_sessions=5),
            _make_timeseries_row(today, sessions=60, ai_sessions=8),
        ]
        traffic_repo.get_source_breakdown.return_value = [
            _make_source_row("google", "organic", False, "", 70),
            _make_source_row("chatgpt.com", "referral", True, "openai", 13),
        ]
        traffic_repo.get_ai_platform_breakdown.return_value = [
            _make_platform_row("openai", 13),
        ]

        result = await service.get_content_detail(
            cid, item.id,
            date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result is not None
        assert result["traffic"] == 110
        assert result["ai_referrals"] == 13
        assert len(result["daily_traffic"]) == 2
        assert len(result["source_breakdown"]) == 2
        assert len(result["ai_platform_breakdown"]) == 1
        assert result["ai_platform_breakdown"][0]["platform"] == "openai"

    @pytest.mark.asyncio
    async def test_source_channel_classification(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        item = _make_inventory_item(company_id=cid)
        inventory_repo.get_by_id.return_value = item

        traffic_repo.get_source_breakdown.return_value = [
            _make_source_row("google", "organic", False, "", 50),
            _make_source_row("(direct)", "(none)", False, "", 30),
            _make_source_row("chatgpt.com", "referral", True, "openai", 20),
        ]

        result = await service.get_content_detail(
            cid, item.id,
            date(2026, 3, 1), date(2026, 3, 28),
        )
        channels = {s["channel"]: s["sessions"] for s in result["source_breakdown"]}
        assert channels["organic"] == 50
        assert channels["direct"] == 30
        assert channels["ai_referral"] == 20


    @pytest.mark.asyncio
    async def test_detail_includes_structural_signals(
        self, service, inventory_repo, traffic_repo,
    ):
        """get_content_detail passes through structural_signals from the inventory item."""
        cid = uuid.uuid4()
        signals_dict = {"word_count": 2450, "has_faq_section": True, "reading_level": 11.5}
        item = _make_inventory_item(company_id=cid)
        item.structural_signals = signals_dict
        inventory_repo.get_by_id.return_value = item

        result = await service.get_content_detail(
            cid, item.id,
            date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result is not None
        assert result["structural_signals"] == signals_dict
        assert result["structural_signals"]["has_faq_section"] is True

    @pytest.mark.asyncio
    async def test_detail_structural_signals_null(
        self, service, inventory_repo, traffic_repo,
    ):
        """Pages without structural_signals return None."""
        cid = uuid.uuid4()
        item = _make_inventory_item(company_id=cid)
        item.structural_signals = None
        inventory_repo.get_by_id.return_value = item

        result = await service.get_content_detail(
            cid, item.id,
            date(2026, 3, 1), date(2026, 3, 28),
        )
        assert result is not None
        assert result["structural_signals"] is None


class TestGetVelocityInsights:
    """Tests for get_velocity_insights()."""

    @pytest.mark.asyncio
    async def test_returns_subset_of_table(self, service, inventory_repo, traffic_repo):
        cid = uuid.uuid4()
        items = [_make_inventory_item(company_id=cid)]
        inventory_repo.get_by_company.return_value = (items, 1)
        traffic_repo.get_per_page_aggregates.return_value = [
            _make_traffic_row("/blog/post", total_sessions=100),
        ]

        result = await service.get_velocity_insights(
            cid, date(2026, 3, 1), date(2026, 3, 28),
        )
        assert len(result) == 1
        assert "velocity" in result[0]
        assert "lifecycle" in result[0]
        assert "velocity_trend" in result[0]
        # Should not include detail fields
        assert "ai_referrals" not in result[0]
        assert "freshness_days" not in result[0]
