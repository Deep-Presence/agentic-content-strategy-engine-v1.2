"""Shared fixtures for research pipeline tests.

Provides: singleton reset, MockDeepAgent, filesystem isolation,
Perplexity mocks, Supabase mirror mocks, settings mocks, input model factories.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.models.artifacts import CompanyResearchInput
from core.models.style_guide import StyleGuideResearchInput


# ---------------------------------------------------------------------------
# 1. Singleton reset — autouse so every test starts clean
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all module-level singletons in research agents before each test."""
    import core.research.agents.base as base_mod
    import core.research.agents.company_research_agent as company_mod
    import core.research.agents.style_guide_agent as style_mod

    orig = {
        "base_backend": base_mod._backend,
        "base_store": base_mod._store,
        "company_agent": company_mod._agent,
        "style_agent": style_mod._agent,
    }

    base_mod._backend = None
    base_mod._store = None
    company_mod._agent = None
    style_mod._agent = None

    yield

    base_mod._backend = orig["base_backend"]
    base_mod._store = orig["base_store"]
    company_mod._agent = orig["company_agent"]
    style_mod._agent = orig["style_agent"]


# ---------------------------------------------------------------------------
# 2. MockDeepAgent
# ---------------------------------------------------------------------------

class MockDeepAgent:
    """Lightweight stand-in for a DeepAgent. Returns configurable messages."""

    def __init__(self, response_content: str = "# Mock Output\n\nTest content."):
        self._response_content = response_content
        self.invoke_calls: list[dict] = []

    def invoke(self, input_dict: dict) -> dict:
        self.invoke_calls.append(input_dict)
        return {
            "messages": [
                {"role": "user", "content": input_dict["messages"][0]["content"]},
                {"role": "assistant", "content": self._response_content},
            ]
        }


@pytest.fixture
def mock_deep_agent():
    """Factory for MockDeepAgent instances."""
    def _factory(response_content: str = "# Mock Output\n\nTest content.") -> MockDeepAgent:
        return MockDeepAgent(response_content=response_content)
    return _factory


# ---------------------------------------------------------------------------
# 3. Patch create_deep_agent across all 3 modules
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_create_deep_agent(mock_deep_agent):
    """Patches create_deep_agent in all 3 agent modules to return a MockDeepAgent.

    Returns the mock agent so tests can inspect invoke_calls or change response.
    """
    agent = mock_deep_agent()
    with (
        patch("core.research.agents.company_research_agent.create_deep_agent", return_value=agent),
        patch("core.research.agents.style_guide_agent.create_deep_agent", return_value=agent),
    ):
        yield agent


# ---------------------------------------------------------------------------
# 4. Mock ChatGoogleGenerativeAI
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_google_chat_model():
    """Patches ChatGoogleGenerativeAI in all 3 agent modules."""
    mock_model = MagicMock()
    with (
        patch("core.research.agents.company_research_agent.ChatGoogleGenerativeAI", return_value=mock_model),
        patch("core.research.agents.style_guide_agent.ChatGoogleGenerativeAI", return_value=mock_model),
    ):
        yield mock_model


# ---------------------------------------------------------------------------
# 5. Mock Perplexity
# ---------------------------------------------------------------------------

CANNED_PERPLEXITY_RESPONSE = (
    "Research findings about Acme Corp.\n\n"
    "Sources:\n[1] https://example.com/acme"
)


@pytest.fixture
def mock_perplexity_research():
    """Patches perplexity_client.research and .search to return canned text."""
    with (
        patch(
            "core.research.tools.perplexity_client.research",
            return_value=CANNED_PERPLEXITY_RESPONSE,
        ),
        patch(
            "core.research.tools.perplexity_client.search",
            return_value=CANNED_PERPLEXITY_RESPONSE,
        ),
    ):
        yield CANNED_PERPLEXITY_RESPONSE


# ---------------------------------------------------------------------------
# 6. Mock Settings
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_research_settings():
    """Provides fake API keys for all research agent settings."""
    with patch("core.research.agents.company_research_agent.settings") as mock_company, \
         patch("core.research.agents.style_guide_agent.settings") as mock_style, \
         patch("core.research.agents.base.settings") as mock_base:
        for m in (mock_company, mock_style, mock_base):
            m.google_api_key_company_deepagent = "fake-google-key"
            m.google_gemini_model_company_deepagent = "gemini-test"
            m.google_api_key_persona_research_deepagent = "fake-google-key"
            m.google_persona_deepagents_model = "gemini-test"
            m.google_api_key_style_guide_research_deepagent = "fake-google-key"
            m.google_style_guide_deepagents_model = "gemini-test"
            m.perplexity_api_key = "fake-perplexity-key"
            m.perplexity_deep_research_model = "sonar-test"
            m.aeo_agent_invoke_timeout_s = 30
        yield mock_company


# ---------------------------------------------------------------------------
# 7. Filesystem isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_artifacts(tmp_path):
    """Redirects _PROJECT_ROOT in all research modules to tmp_path.

    Creates the standard artifact subdirectories so writes succeed.
    Returns tmp_path for assertions.
    """
    for subdir in [
        "artifacts/company_context",
        "artifacts/personas",
        "artifacts/style_guides",
        "artifacts/_logs",
    ]:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)

    modules_to_patch = [
        "core.research.graphs.company_research._PROJECT_ROOT",
        "core.research.graphs.style_guide._PROJECT_ROOT",
        "core.research.agents.base._PROJECT_ROOT",
        "core.research.agents.style_guide_agent._PROJECT_ROOT",
    ]
    patches = [patch(m, tmp_path) for m in modules_to_patch]
    for p in patches:
        p.start()
    yield tmp_path
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# 8. Mock Supabase mirrors
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_supabase_mirrors():
    """Patches all three mirror_*_if_configured functions to no-op."""
    with (
        patch("core.research.graphs.company_research.mirror_company_context_if_configured", return_value=None),
        patch("core.research.graphs.style_guide.mirror_styleguide_if_configured", return_value=None),
    ):
        yield


# ---------------------------------------------------------------------------
# 9. Input model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def company_input() -> CompanyResearchInput:
    return CompanyResearchInput(
        company_name="Acme Corp",
        domain="acme.com",
    )


@pytest.fixture
def style_input() -> StyleGuideResearchInput:
    return StyleGuideResearchInput(
        company_name="Acme Corp",
        domain="acme.com",
        company_slug="acme-corp",
        company_context_path="/artifacts/company_context/acme-corp.md",
        persona_paths=["/artifacts/personas/acme-corp__persona-icp.md"],
    )
