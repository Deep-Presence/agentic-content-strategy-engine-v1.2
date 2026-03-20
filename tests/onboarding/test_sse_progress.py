"""Test that the onboarding orchestrator emits progress_pct events.

No real LLM calls — all sub-pipelines are mocked.
Verifies the progress counter increments correctly.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.onboarding import OnboardingInput, OnboardingPhase
from core.onboarding.orchestrator import run_onboarding_pipeline

# Patch targets — must match real import locations (not the orchestrator)
_SA_PATCH = "core.site_audit.pipeline.run_site_audit"
_KB_PATCH = "core.research.knowledge_base.pipeline.run_knowledge_base_pipeline"
_AP_PATCH = "core.research.audience_persona.pipeline.run_audience_persona_pipeline"
_VSG_PATCH = "core.research.voice_style_guide.pipeline.run_voice_style_guide_pipeline"
_GA_PATCH = "core.gap_analysis.pipeline.run_gap_analysis"
_TD_PATCH = "core.topic_discovery.pipeline.run_topic_discovery_pipeline"


def _make_input(**overrides) -> OnboardingInput:
    defaults = dict(
        company_name="Test Co",
        domain="test.com",
        company_slug="test-co",
        phases=[OnboardingPhase.phase_a, OnboardingPhase.phase_b, OnboardingPhase.phase_c],
    )
    defaults.update(overrides)
    return OnboardingInput(**defaults)


class FakeEventBus:
    """Captures all published events for assertion."""

    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    def publish(self, task_id: str, event_type: str, data: dict) -> None:
        self.events.append((task_id, event_type, data))

    def get_events_by_type(self, event_type: str) -> list[dict]:
        return [data for _, et, data in self.events if et == event_type]

    def get_event_types(self) -> list[str]:
        return [et for _, et, _ in self.events]


def _mock_sa():
    r = MagicMock()
    r.status = "completed"
    r.audit_id = "audit-1"
    r.pages_crawled = 50
    return r


def _mock_sa_fail():
    r = MagicMock()
    r.status = "failed"
    r.error_message = "crawl failed"
    r.audit_id = ""
    r.pages_crawled = 0
    return r


def _mock_kb():
    o = MagicMock()
    o.company_profile_path = "artifacts/company_context/test-co.md"
    return o


def _mock_ap():
    o = MagicMock()
    o.persona_dir = "artifacts/audience_personas/test-co"
    o.profiles_generated = 3
    return o


def _mock_vsg():
    o = MagicMock()
    o.style_guide_path = "artifacts/style_guides/test-co.md"
    return o


def _mock_ga():
    o = MagicMock()
    o.slug = "test-co"
    return o


def _mock_td():
    o = MagicMock()
    o.total_subdomains_discovered = 25
    return o


@pytest.mark.asyncio
@patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td())
@patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga())
@patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg())
@patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap())
@patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb())
@patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa())
async def test_progress_events_emitted_for_all_six_subs(sa, kb, ap, vsg, ga, td):
    bus = FakeEventBus()
    await run_onboarding_pipeline(_make_input(), task_id="t-1", event_bus=bus)

    progress_events = bus.get_events_by_type("progress")
    pcts = [e["progress_pct"] for e in progress_events]

    assert len(progress_events) == 6, f"Expected 6 progress events, got {len(progress_events)}: {pcts}"
    assert pcts[-1] == 100
    for i in range(1, len(pcts)):
        assert pcts[i] > pcts[i - 1], f"Not increasing: {pcts}"


@pytest.mark.asyncio
@patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td())
@patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga())
@patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg())
@patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap())
@patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb())
@patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa())
async def test_progress_increments_correctly(sa, kb, ap, vsg, ga, td):
    bus = FakeEventBus()
    await run_onboarding_pipeline(_make_input(), task_id="t-1", event_bus=bus)

    pcts = [e["progress_pct"] for e in bus.get_events_by_type("progress")]
    expected = [16, 33, 50, 66, 83, 100]
    assert pcts == expected, f"Expected {expected}, got {pcts}"


@pytest.mark.asyncio
@patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td())
@patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga())
@patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg())
@patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap())
@patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb())
@patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa_fail())
async def test_progress_emitted_even_on_failure(sa, kb, ap, vsg, ga, td):
    bus = FakeEventBus()
    await run_onboarding_pipeline(_make_input(), task_id="t-1", event_bus=bus)

    progress_events = bus.get_events_by_type("progress")
    assert len(progress_events) == 6, f"SA failed but should still emit 6 progress events"


@pytest.mark.asyncio
@patch(_TD_PATCH, new_callable=AsyncMock, return_value=_mock_td())
@patch(_GA_PATCH, new_callable=AsyncMock, return_value=_mock_ga())
@patch(_VSG_PATCH, new_callable=AsyncMock, return_value=_mock_vsg())
@patch(_AP_PATCH, new_callable=AsyncMock, return_value=_mock_ap())
@patch(_KB_PATCH, new_callable=AsyncMock, return_value=_mock_kb())
@patch(_SA_PATCH, new_callable=AsyncMock, return_value=_mock_sa())
async def test_terminal_completed_event_emitted_last(sa, kb, ap, vsg, ga, td):
    bus = FakeEventBus()
    await run_onboarding_pipeline(_make_input(), task_id="t-1", event_bus=bus)

    event_types = bus.get_event_types()
    assert event_types[-1] == "completed"
    assert bus.get_events_by_type("completed")[0]["onboarding_status"] == "completed"
