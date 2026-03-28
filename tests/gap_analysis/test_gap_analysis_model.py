"""Tests for GapAnalysisInput model validators."""

from core.models.gap_analysis import GapAnalysisInput


class TestKnowledgeDocSlugBackfill:
    """H5: knowledge_doc_dir → knowledge_doc_slug backward compat."""

    def test_backfill_slug_from_dir(self):
        m = GapAnalysisInput(
            company_name="Test Co",
            knowledge_doc_dir="/path/to/knowledge_docs/ramp",
        )
        assert m.knowledge_doc_slug == "ramp"

    def test_slug_takes_precedence_over_dir(self):
        m = GapAnalysisInput(
            company_name="Test Co",
            knowledge_doc_dir="/path/to/knowledge_docs/ramp",
            knowledge_doc_slug="explicit-slug",
        )
        assert m.knowledge_doc_slug == "explicit-slug"

    def test_no_backfill_when_both_none(self):
        m = GapAnalysisInput(company_name="Test Co")
        assert m.knowledge_doc_slug is None
        assert m.knowledge_doc_dir is None

    def test_backfill_with_trailing_slash(self):
        m = GapAnalysisInput(
            company_name="Test Co",
            knowledge_doc_dir="/path/to/ramp/",
        )
        assert m.knowledge_doc_slug == "ramp"

    def test_backfill_relative_path(self):
        m = GapAnalysisInput(
            company_name="Test Co",
            knowledge_doc_dir="knowledge_docs/acme-corp",
        )
        assert m.knowledge_doc_slug == "acme-corp"
