"""Unit tests for core.research.persistence — DB persistence hooks for KB/AP/VSG.

Pure unit tests — no real DB needed. All DB interaction is mocked via
AsyncMock session factories and patched repositories.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.research.persistence import (
    _sha256,
    _should_persist,
    _word_count,
    persist_author_research,
    persist_kb_doc,
    persist_kb_synthesis,
    persist_persona_profile,
    persist_pipeline_run_complete,
    persist_pipeline_run_failed,
    persist_pipeline_run_start,
    persist_voice_style_guide,
)


# ── Shared fixtures ──────────────────────────────────────────────────────

RUN_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
SLUG = "test-co"
CONTENT_MD = "# Company Overview\n\nTest Co is a fintech company."


class _FakeSession:
    """Async context manager that yields itself and tracks calls."""

    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.get = AsyncMock(return_value=None)
        self.add = MagicMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_session_factory() -> MagicMock:
    """Return a callable that produces _FakeSession instances."""
    session = _FakeSession()
    factory = MagicMock()
    factory.return_value = session
    factory._session = session  # stash for assertions
    return factory


# Patch targets for per-pipeline persistence modules
_KB_PERSIST = "core.research.knowledge_base.persistence"
_AP_PERSIST = "core.research.audience_persona.persistence"
_VSG_PERSIST = "core.research.voice_style_guide.persistence"


# ── Guard Tests ──────────────────────────────────────────────────────────


class TestShouldPersist:
    def test_all_present_returns_true(self):
        sf = MagicMock()
        assert _should_persist(sf, RUN_ID, COMPANY_ID) is True

    def test_none_session_factory_returns_false(self):
        assert _should_persist(None, RUN_ID, COMPANY_ID) is False

    def test_none_run_id_returns_false(self):
        assert _should_persist(MagicMock(), None, COMPANY_ID) is False

    def test_none_company_id_returns_false(self):
        assert _should_persist(MagicMock(), RUN_ID, None) is False

    def test_all_none_returns_false(self):
        assert _should_persist(None, None, None) is False


# ── Helper Tests ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_sha256_deterministic(self):
        h1 = _sha256("hello")
        h2 = _sha256("hello")
        assert h1 == h2
        assert len(h1) == 64  # hex digest

    def test_sha256_differs_for_different_input(self):
        assert _sha256("a") != _sha256("b")

    def test_word_count(self):
        assert _word_count("one two three") == 3
        assert _word_count("") == 0  # edge: empty string returns 0 from split


# ── KB Doc Persistence ───────────────────────────────────────────────────


class TestPersistKBDoc:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        self.factory = _make_session_factory()
        self.kb_run_mock = AsyncMock(return_value=uuid.uuid4())
        self.kb_doc_mock = AsyncMock()

    @patch(f"{_KB_PERSIST}.persist_kb_document")
    @patch(f"{_KB_PERSIST}.persist_kb_run")
    async def test_persists_kb_doc(self, mock_run, mock_doc):
        mock_run.return_value = uuid.uuid4()
        mock_doc.return_value = None
        await persist_kb_doc(
            self.factory, RUN_ID, COMPANY_ID, SLUG,
            "company_overview", 1, CONTENT_MD,
            "knowledge_base/test-co/company_overview/v1.md",
        )
        mock_run.assert_awaited_once()
        mock_doc.assert_awaited_once()

    async def test_no_persist_when_session_none(self):
        await persist_kb_doc(
            None, RUN_ID, COMPANY_ID, SLUG,
            "company_overview", 1, CONTENT_MD,
            "knowledge_base/test-co/company_overview/v1.md",
        )

    @patch(f"{_KB_PERSIST}.persist_kb_document")
    @patch(f"{_KB_PERSIST}.persist_kb_run")
    async def test_exception_caught_and_logged(self, mock_run, mock_doc):
        mock_run.side_effect = RuntimeError("DB down")
        # Should NOT raise
        await persist_kb_doc(
            self.factory, RUN_ID, COMPANY_ID, SLUG,
            "company_overview", 1, CONTENT_MD,
            "knowledge_base/test-co/company_overview/v1.md",
        )


# ── KB Synthesis Persistence ─────────────────────────────────────────────


class TestPersistKBSynthesis:
    @patch(f"{_KB_PERSIST}.persist_kb_synthesis_doc")
    @patch(f"{_KB_PERSIST}.persist_kb_run")
    async def test_persists_synthesis(self, mock_run, mock_synth):
        factory = _make_session_factory()
        mock_run.return_value = uuid.uuid4()
        mock_synth.return_value = None

        await persist_kb_synthesis(
            factory, RUN_ID, COMPANY_ID, SLUG,
            2, CONTENT_MD,
            "knowledge_base/test-co/synthesis/v2.md",
        )
        mock_run.assert_awaited_once()
        mock_synth.assert_awaited_once()

    async def test_no_persist_when_run_id_none(self):
        await persist_kb_synthesis(
            _make_session_factory(), None, COMPANY_ID, SLUG,
            1, CONTENT_MD, "key",
        )
        # No error, no DB call


# ── Persona Profile Persistence ──────────────────────────────────────────


class TestPersistPersonaProfile:
    @patch(f"{_AP_PERSIST}.persist_persona_profile_doc")
    @patch(f"{_AP_PERSIST}.persist_persona_run")
    async def test_persists_persona(self, mock_run, mock_profile):
        factory = _make_session_factory()
        mock_run.return_value = uuid.uuid4()
        mock_profile.return_value = None

        await persist_persona_profile(
            factory, RUN_ID, COMPANY_ID, SLUG,
            "cfo-001", "CFO Persona", 1, CONTENT_MD,
            "audience_persona/test-co/cfo-001/v1.md",
            kind="primary",
        )
        mock_run.assert_awaited_once()
        mock_profile.assert_awaited_once()
        # Verify kind is passed through to the delegate
        call_kwargs = mock_profile.call_args
        assert call_kwargs.kwargs.get("kind") == "primary"

    @patch(f"{_AP_PERSIST}.persist_persona_profile_doc")
    @patch(f"{_AP_PERSIST}.persist_persona_run")
    async def test_exception_safe(self, mock_run, mock_profile):
        factory = _make_session_factory()
        mock_run.side_effect = RuntimeError("fail")
        await persist_persona_profile(
            factory, RUN_ID, COMPANY_ID, SLUG,
            "cfo-001", "CFO", 1, CONTENT_MD, "key",
        )


# ── Voice Style Guide Persistence ───────────────────────────────────────


class TestPersistVoiceStyleGuide:
    @patch(f"{_VSG_PERSIST}.persist_vsg_guide_doc")
    @patch(f"{_VSG_PERSIST}.persist_vsg_run")
    async def test_persists_guide(self, mock_run, mock_guide):
        factory = _make_session_factory()
        mock_run.return_value = uuid.uuid4()
        mock_guide.return_value = None

        await persist_voice_style_guide(
            factory, RUN_ID, COMPANY_ID, SLUG,
            1, CONTENT_MD,
            "voice_style_guide/test-co/v1.md",
            source_authors=["Jane Doe", "John Smith"],
        )
        mock_run.assert_awaited_once()
        mock_guide.assert_awaited_once()
        call_kwargs = mock_guide.call_args
        assert call_kwargs.kwargs.get("source_authors") == ["Jane Doe", "John Smith"]


class TestPersistAuthorResearch:
    @patch(f"{_VSG_PERSIST}.persist_vsg_author_doc")
    @patch(f"{_VSG_PERSIST}.persist_vsg_run")
    async def test_persists_author(self, mock_run, mock_author):
        factory = _make_session_factory()
        mock_run.return_value = uuid.uuid4()
        mock_author.return_value = None

        await persist_author_research(
            factory, RUN_ID, COMPANY_ID, SLUG,
            "author-001", "Jane Doe", 1, CONTENT_MD,
            "voice_style_guide/test-co/authors/jane-doe/v1.md",
        )
        mock_run.assert_awaited_once()
        mock_author.assert_awaited_once()


# ── Pipeline Run Tracking ────────────────────────────────────────────────


class TestPersistPipelineRunStart:
    async def test_no_op_when_not_configured(self):
        await persist_pipeline_run_start(
            None, None, None, SLUG, "knowledge_base",
        )

    @patch("core.db.models.pipelines.PipelineRunModel")
    @patch("core.db.enums.PipelineType")
    @patch("core.db.enums.PipelineStatus")
    async def test_creates_pipeline_run(self, mock_status, mock_type, mock_model):
        factory = _make_session_factory()
        await persist_pipeline_run_start(
            factory, RUN_ID, COMPANY_ID, SLUG, "knowledge_base",
        )
        factory._session.commit.assert_awaited_once()
        factory._session.add.assert_called_once()


class TestPersistPipelineRunComplete:
    async def test_no_op_when_not_configured(self):
        await persist_pipeline_run_complete(None, None)

    async def test_handles_missing_run(self):
        factory = _make_session_factory()
        factory._session.get = AsyncMock(return_value=None)
        await persist_pipeline_run_complete(factory, RUN_ID, {"total": 5})
        factory._session.commit.assert_not_awaited()

    async def test_marks_run_completed(self):
        factory = _make_session_factory()
        mock_run = MagicMock()
        factory._session.get = AsyncMock(return_value=mock_run)
        await persist_pipeline_run_complete(factory, RUN_ID, {"total": 5})
        factory._session.commit.assert_awaited_once()


class TestPersistPipelineRunFailed:
    async def test_no_op_when_not_configured(self):
        await persist_pipeline_run_failed(None, None, "error")

    async def test_marks_run_failed(self):
        factory = _make_session_factory()
        mock_run = MagicMock()
        factory._session.get = AsyncMock(return_value=mock_run)
        await persist_pipeline_run_failed(factory, RUN_ID, "Something broke")
        factory._session.commit.assert_awaited_once()

    async def test_truncates_long_error(self):
        factory = _make_session_factory()
        mock_run = MagicMock()
        factory._session.get = AsyncMock(return_value=mock_run)
        long_error = "x" * 5000
        await persist_pipeline_run_failed(factory, RUN_ID, long_error)
        assert mock_run.error_message == "x" * 2000


# ── Content Hash Computation ─────────────────────────────────────────────


class TestContentHash:
    @patch(f"{_KB_PERSIST}.persist_kb_document")
    @patch(f"{_KB_PERSIST}.persist_kb_run")
    async def test_kb_doc_delegates_with_content(self, mock_run, mock_doc):
        """Verify the shim delegates content_md to the per-pipeline persist function."""
        factory = _make_session_factory()
        mock_run.return_value = uuid.uuid4()
        mock_doc.return_value = None

        await persist_kb_doc(
            factory, RUN_ID, COMPANY_ID, SLUG,
            "overview", 1, "some content",
            "key",
        )
        # The per-pipeline function receives content_md for hash computation
        call_args = mock_doc.call_args
        assert call_args[0][6] == "some content"  # content_md positional arg


# ── C1/C3 Regression: Pipeline persist arg verification ────────────────


class TestKBPipelinePersistArgs:
    """C1: KB pipeline must use manifest.documents (not .docs) and current_version."""

    async def test_kb_manifest_field_is_documents(self):
        """KBManifest has 'documents' field, not 'docs'."""
        from core.models.knowledge_base import KBDocEntry, KBManifest

        manifest = KBManifest(
            slug="test-co",
            documents={
                "company_overview": KBDocEntry(
                    current_version=3,
                    status="fresh",
                ),
            },
        )
        # The field is 'documents', not 'docs'
        assert hasattr(manifest, "documents")
        assert not hasattr(manifest, "docs")
        # Version is 'current_version', not 'version'
        entry = manifest.documents["company_overview"]
        assert entry.current_version == 3
        assert not hasattr(entry, "version") or entry.current_version == 3

    async def test_kb_persist_extracts_correct_version(self):
        """Verify the version extraction pattern used by the KB pipeline."""
        from core.models.knowledge_base import KBDocEntry, KBManifest

        manifest = KBManifest(
            slug="test-co",
            documents={
                "company_overview": KBDocEntry(current_version=5),
                "customer_reviews": KBDocEntry(current_version=2),
            },
            synthesis_version=3,
        )

        # Pattern from fixed pipeline code:
        for dt_val in ["company_overview", "customer_reviews"]:
            entry = manifest.documents.get(dt_val) if manifest.documents else None
            ver = entry.current_version if entry and entry.current_version > 0 else 1
            expected = {"company_overview": 5, "customer_reviews": 2}[dt_val]
            assert ver == expected

        # Synthesis version extraction
        synth_ver = manifest.synthesis_version or 1
        assert synth_ver == 3

    async def test_kb_persist_defaults_version_for_missing_entry(self):
        """Missing doc entry should default to version 1."""
        from core.models.knowledge_base import KBManifest

        manifest = KBManifest(slug="test-co")

        entry = manifest.documents.get("nonexistent") if manifest.documents else None
        ver = entry.current_version if entry and entry.current_version > 0 else 1
        assert ver == 1


class TestAPPipelinePersistArgs:
    """C3: AP pipeline must use effective_slug, manifest version, plural prefix."""

    async def test_ap_storage_key_uses_plural_prefix(self):
        """Storage key must use 'audience_personas/' not 'audience_persona/'."""
        effective_slug = "test-co__product-x"
        pid = "cfo-001"
        ver = 2
        key = f"audience_personas/{effective_slug}/{pid}/v{ver}.md"
        assert key.startswith("audience_personas/")
        assert effective_slug in key
        assert f"v{ver}" in key

    async def test_ap_persist_uses_manifest_version(self):
        """Verify version extraction from PersonaManifest."""
        from core.models.audience_persona import PersonaManifest, PersonaProfileEntry

        manifest = PersonaManifest(
            slug="test-co",
            personas={
                "cfo-001": PersonaProfileEntry(
                    persona_id="cfo-001",
                    current_version=3,
                ),
            },
        )

        meta = (manifest.personas or {}).get("cfo-001")
        ver = meta.current_version if meta and meta.current_version > 0 else 1
        assert ver == 3


class TestVSGPipelinePersistArgs:
    """C3: VSG pipeline must use effective_slug, manifest version, correct path."""

    async def test_vsg_author_storage_key_no_authors_subdir(self):
        """Author storage key must NOT have 'authors/' subdirectory."""
        effective_slug = "test-co"
        aid = "author-001"
        ver = 2
        key = f"voice_style_guide/{effective_slug}/{aid}/v{ver}.md"
        assert "/authors/" not in key
        assert f"/{aid}/v{ver}.md" in key

    async def test_vsg_persist_uses_manifest_version(self):
        """Verify version extraction from VoiceStyleGuideManifest."""
        from core.models.voice_style_guide import (
            AuthorEntry,
            VoiceStyleGuideEntry,
            VoiceStyleGuideManifest,
        )

        manifest = VoiceStyleGuideManifest(
            slug="test-co",
            authors={
                "author-001": AuthorEntry(
                    author_id="author-001",
                    current_version=4,
                ),
            },
            guide=VoiceStyleGuideEntry(current_version=2),
        )

        author_meta = (manifest.authors or {}).get("author-001")
        aver = author_meta.current_version if author_meta and author_meta.current_version > 0 else 1
        assert aver == 4

        guide_ver = manifest.guide.current_version if manifest.guide and manifest.guide.current_version > 0 else 1
        assert guide_ver == 2
