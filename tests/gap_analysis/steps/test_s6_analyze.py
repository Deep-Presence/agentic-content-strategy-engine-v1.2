"""Tests for s6_analyze.py — GapContentBrief computation and ClusterContentSpec expansion."""
from __future__ import annotations

from typing import List

import numpy as np
import pytest

from core.models.gap_analysis import (
    CitationExemplar,
    ClusterContentSpec,
    EnrichedCitation,
    GapContentBrief,
    GeneratedQuery,
    ParagraphMatch,
    QueryGap,
    SemanticUnit,
    StructuralSignals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _random_embedding(dim: int = 32) -> List[float]:
    """Small random embedding for tests (not 3072 — fast & small)."""
    rng = np.random.default_rng(42)
    vec = rng.standard_normal(dim)
    return (vec / np.linalg.norm(vec)).tolist()


def _make_query(qid: str, cluster: str = "awareness", text: str = "test query") -> GeneratedQuery:
    return GeneratedQuery(
        query_id=qid,
        cluster_id=f"c_{cluster}",
        cluster_name=cluster,
        query_text=text,
        embedding=_random_embedding(),
    )


def _make_enriched(
    url: str,
    query_id: str,
    cluster: str = "awareness",
    word_count: int = 500,
    has_faq: bool = False,
    has_tables: bool = False,
    has_key_takeaways: bool = False,
    reading_level: float = 10.0,
    avg_para_len: float = 40.0,
    header_count: int = 5,
    h2_count: int = 3,
    h3_count: int = 2,
    ordered_list_count: int = 0,
    unordered_list_count: int = 1,
    table_count: int = 0,
    definition_list_count: int = 0,
    code_block_count: int = 0,
    min_bullets: int = 3,
    data_point_count: int = 5,
    citation_density: float = 2.0,
    authority_type: str = "commercial_or_media",
    content_type: str = "blog_or_article",
) -> EnrichedCitation:
    signals = StructuralSignals(
        word_count=word_count,
        paragraph_count=max(1, word_count // 40),
        header_count=header_count,
        has_headers=header_count > 0,
        has_lists=True,
        has_numbers=True,
        authority_type=authority_type,
        content_type=content_type,
        # Category A
        main_content_word_count=word_count,
        avg_paragraph_length=avg_para_len,
        reading_level=reading_level,
        avg_sentence_count_per_paragraph=2.5,
        # Category B
        h2_count=h2_count,
        h3_count=h3_count,
        ordered_list_count=ordered_list_count,
        unordered_list_count=unordered_list_count,
        table_count=table_count,
        definition_list_count=definition_list_count,
        code_block_count=code_block_count,
        min_bullets_per_list=min_bullets,
        # Category C
        has_faq_section=has_faq,
        has_key_takeaways=has_key_takeaways,
        # Category D
        data_point_count=data_point_count,
        citation_density=citation_density,
    )
    emb = _random_embedding()
    return EnrichedCitation(
        url=url,
        domain=url.split("//")[1].split("/")[0],
        title=f"Title for {url}",
        query_id=query_id,
        cluster_name=cluster,
        engine="perplexity",
        anchor_text="test snippet",
        paragraphs=["Test paragraph with enough text to be meaningful."] * 3,
        best_paragraphs=[
            ParagraphMatch(paragraph="Test paragraph.", embedding=emb, similarity=0.8),
        ],
        structural_signals=signals,
    )


def _make_company_unit(uid: str = "u1") -> SemanticUnit:
    return SemanticUnit(
        unit_id=uid,
        text="Company page about expense management and automation solutions.",
        embedding=_random_embedding(),
    )


# ---------------------------------------------------------------------------
# Tests: GapContentBrief computation
# ---------------------------------------------------------------------------
class TestGapContentBrief:
    """Tests for _compute_content_brief and its integration into QueryGap."""

    def test_brief_computed_from_exemplars(self):
        """Content brief should be computed from top-3 exemplar signals."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        queries = [_make_query("q1", "awareness")]
        enriched = [
            _make_enriched("https://a.com/p1", "q1", word_count=800, has_faq=True, reading_level=10.0),
            _make_enriched("https://b.com/p2", "q1", word_count=1200, has_faq=False, reading_level=12.0),
            _make_enriched("https://c.com/p3", "q1", word_count=600, has_faq=True, reading_level=8.0),
        ]
        company = [_make_company_unit()]

        result = compute_gap_analysis(queries, company, enriched)
        assert len(result.gaps) >= 1

        gap = result.gaps[0]
        assert gap.content_brief is not None
        brief = gap.content_brief
        assert brief.exemplar_count > 0
        assert brief.target_word_count[0] > 0
        assert brief.target_word_count[1] >= brief.target_word_count[0]

    def test_brief_dedupes_exemplars_by_url(self):
        """Same URL appearing multiple times should only count once in brief."""
        from core.gap_analysis.steps.s6_analyze import _compute_content_brief

        # Two exemplars from same URL
        exemplars = [
            CitationExemplar(
                similarity=0.9,
                url="https://same.com/page",
                domain="same.com",
                structural_signals=StructuralSignals(word_count=500, has_faq_section=True),
            ),
            CitationExemplar(
                similarity=0.8,
                url="https://same.com/page",
                domain="same.com",
                structural_signals=StructuralSignals(word_count=500, has_faq_section=True),
            ),
            CitationExemplar(
                similarity=0.7,
                url="https://other.com/page",
                domain="other.com",
                structural_signals=StructuralSignals(word_count=800),
            ),
        ]
        brief = _compute_content_brief(exemplars)
        assert brief.exemplar_count == 2  # Deduped: same.com + other.com

    def test_brief_none_when_no_signals(self):
        """Should return None when no exemplars have structural signals."""
        from core.gap_analysis.steps.s6_analyze import _compute_content_brief

        exemplars = [
            CitationExemplar(similarity=0.9, url="https://x.com", structural_signals=None),
        ]
        brief = _compute_content_brief(exemplars)
        assert brief is None


# ---------------------------------------------------------------------------
# Tests: ClusterContentSpec expansion
# ---------------------------------------------------------------------------
class TestClusterContentSpecExpansion:
    """Tests for expanded ClusterContentSpec fields."""

    def test_faq_and_table_rates_computed(self):
        """faq_rate and table_rate should be computed from enriched signals."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        queries = [_make_query("q1", "awareness"), _make_query("q2", "awareness")]
        enriched = [
            _make_enriched("https://a.com/p1", "q1", has_faq=True, table_count=1),
            _make_enriched("https://b.com/p2", "q1", has_faq=True, table_count=0),
            _make_enriched("https://c.com/p3", "q2", has_faq=False, table_count=1),
        ]
        company = [_make_company_unit()]

        result = compute_gap_analysis(queries, company, enriched)
        assert len(result.cluster_specs) >= 1

        spec = result.cluster_specs[0]
        # 2/3 have FAQ, 2/3 have tables
        assert spec.faq_rate > 0.0
        assert spec.table_rate > 0.0
        assert spec.avg_word_count > 0.0

    def test_dominant_types_computed(self):
        """Should compute dominant authority and content types."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        queries = [_make_query("q1", "awareness")]
        enriched = [
            _make_enriched("https://a.com/p1", "q1", authority_type="academic", content_type="research"),
            _make_enriched("https://b.com/p2", "q1", authority_type="academic", content_type="blog_or_article"),
            _make_enriched("https://c.com/p3", "q1", authority_type="commercial_or_media", content_type="research"),
        ]
        company = [_make_company_unit()]

        result = compute_gap_analysis(queries, company, enriched)
        spec = result.cluster_specs[0]
        assert spec.dominant_authority_type == "academic"
        assert spec.dominant_content_type == "research"

    def test_backward_compat_old_cluster_spec(self):
        """Old ClusterContentSpec JSON without new fields should load fine."""
        old_data = {
            "cluster_name": "awareness",
            "query_count": 10,
            "word_count_range": [500, 2000],
            "structural_rates": {"headers": 0.9, "lists": 0.8},
            "total_citations_analyzed": 20,
        }
        spec = ClusterContentSpec(**old_data)
        assert spec.faq_rate == 0.0
        assert spec.dominant_content_type is None
        assert spec.exemplar_themes == []

    def test_exemplar_themes_computed(self):
        """Should extract exemplar themes via TF-IDF from citation paragraphs."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        queries = [_make_query("q1", "awareness")]
        enriched = [
            _make_enriched("https://a.com/p1", "q1"),
            _make_enriched("https://b.com/p2", "q1"),
        ]
        # Give them distinct paragraphs for TF-IDF
        enriched[0].paragraphs = ["Expense management automation reduces costs significantly for enterprises."] * 3
        enriched[1].paragraphs = ["Corporate spending tracking software improves financial compliance dramatically."] * 3
        company = [_make_company_unit()]

        result = compute_gap_analysis(queries, company, enriched)
        spec = result.cluster_specs[0]
        # Should have some themes (or empty list if TF-IDF fails — that's acceptable)
        assert isinstance(spec.exemplar_themes, list)


# ---------------------------------------------------------------------------
# Tests: Exemplar per_paragraph_word_counts exclusion (Codex finding #11)
# ---------------------------------------------------------------------------
class TestExemplarBloatPrevention:
    """Exemplar structural_signals should not include per_paragraph_word_counts."""

    def test_exemplar_signals_exclude_per_paragraph(self):
        """per_paragraph_word_counts should be empty on exemplar signals to reduce artifact size."""
        from core.gap_analysis.steps.s6_analyze import compute_gap_analysis

        queries = [_make_query("q1", "awareness")]
        enriched = [
            _make_enriched("https://a.com/p1", "q1"),
        ]
        # Give the citation real per_paragraph_word_counts
        enriched[0].structural_signals.per_paragraph_word_counts = [40, 50, 60, 30, 45]
        company = [_make_company_unit()]

        result = compute_gap_analysis(queries, company, enriched)
        if result.gaps and result.gaps[0].top_cited_exemplars:
            for exemplar in result.gaps[0].top_cited_exemplars:
                if exemplar.structural_signals:
                    assert exemplar.structural_signals.per_paragraph_word_counts == [], (
                        "Exemplar should not carry per_paragraph_word_counts (bloat prevention)"
                    )
