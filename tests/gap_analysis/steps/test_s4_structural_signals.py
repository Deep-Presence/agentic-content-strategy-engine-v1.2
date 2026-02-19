"""Tests for expanded StructuralSignals extraction — TDD: written BEFORE implementation."""
from __future__ import annotations

import pytest

from core.models.gap_analysis import StructuralSignals


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------
RICH_ARTICLE_HTML = """
<html><body>
<article>
  <h1>The Ultimate Guide to Corporate Expense Management</h1>
  <p>Corporate expense management is the process of tracking, approving, and reporting on business expenses. According to a 2024 study by Aberdeen Group, companies that automate expense management save 65% on processing costs. This comprehensive guide covers everything you need to know.</p>

  <h2>Key Takeaways</h2>
  <ul>
    <li>Automated expense management reduces processing time by an average of 75% compared to manual systems.</li>
    <li>Companies using modern expense tools report 40% fewer policy violations and improved compliance overall.</li>
    <li>Integration with accounting software eliminates duplicate data entry and reduces errors by significant amounts.</li>
  </ul>

  <h2>What Is Expense Management?</h2>
  <p>Expense management refers to the systems and processes a company uses to process, pay, and audit employee-initiated expenses. These costs include travel and entertainment expenses, company credit card charges, and other reimbursable business expenditures that require formal tracking and approval.</p>

  <h3>Types of Business Expenses</h3>
  <p>Business expenses fall into several categories. Travel expenses account for approximately 30% of total corporate spending. Entertainment and meals make up another 15%. Technology and software subscriptions represent a growing 20% share of most company budgets in the modern enterprise landscape.</p>

  <h2>Frequently Asked Questions</h2>
  <details>
    <summary>How much does expense management software cost?</summary>
    <p>Most expense management platforms charge between $5 and $25 per user per month. Enterprise plans with advanced features and integrations typically cost more than standard plans but offer significant returns.</p>
  </details>
  <details>
    <summary>Can expense management integrate with our ERP?</summary>
    <p>Yes, most modern expense management tools offer native integrations with popular ERP systems like SAP, Oracle, and NetSuite through their extensive API and connector ecosystems.</p>
  </details>

  <h2>Step-by-Step Implementation</h2>
  <ol>
    <li>Step 1: Audit your current expense process and identify bottlenecks in the existing manual workflow system.</li>
    <li>Step 2: Select an expense management platform that meets your specific organizational requirements and budget.</li>
    <li>Step 3: Configure policies and approval workflows based on your company's internal governance framework.</li>
    <li>Step 4: Train employees on the new system and provide adequate documentation for self-service support.</li>
    <li>Step 5: Monitor adoption metrics and optimize the workflow based on ongoing feedback from the user base.</li>
  </ol>

  <table>
    <tr><th>Feature</th><th>Basic Plan</th><th>Enterprise Plan</th></tr>
    <tr><td>Receipt scanning</td><td>Yes</td><td>Yes</td></tr>
    <tr><td>Policy enforcement</td><td>Limited</td><td>Full</td></tr>
    <tr><td>ERP integration</td><td>No</td><td>Yes</td></tr>
  </table>

  <blockquote>"Automating expense management was the single most impactful operational change we made last year," says Jane Smith, CFO of TechCorp International, a Fortune 500 technology company with operations across multiple continents.</blockquote>

  <p>According to Gartner research published in 2024, 78% of enterprises plan to fully automate their expense management workflows within the next two years. The research also indicates that early adopters achieve $12.50 in savings for every dollar invested in the automation effort.</p>

  <a href="https://example.com/report">Full Research Report</a>
  <a href="https://example.com/demo">Request a Demo</a>
</article>
</body></html>
"""

MINIMAL_HTML = """
<html><body>
<p>A single short paragraph with not much content at all to extract here.</p>
</body></html>
"""

FAQ_HTML = """
<html><body>
<article>
  <h1>Frequently Asked Questions About Expense Management Software</h1>
  <dl>
    <dt>What is expense management?</dt>
    <dd>Expense management is the process by which businesses track and reimburse employee-initiated spending on goods and services.</dd>
    <dt>How much does it cost?</dt>
    <dd>Pricing ranges from five dollars to twenty-five dollars per user per month depending on features and scale of deployment.</dd>
  </dl>
</article>
</body></html>
"""

CODE_BLOCK_HTML = """
<html><body>
<article>
  <h1>API Documentation for Expense Management Platform Integration</h1>
  <p>This guide shows how to integrate with our expense management API endpoint to submit receipts programmatically.</p>
  <pre><code>curl -X POST https://api.example.com/expenses -H "Authorization: Bearer token" -d '{"amount": 42.50}'</code></pre>
  <pre><code>response = requests.post("https://api.example.com/expenses", json={"amount": 42.50})</code></pre>
  <p>The API returns a JSON response with the created expense object including a unique identifier for tracking purposes.</p>
</article>
</body></html>
"""

NON_ENGLISH_HTML = """
<html><body>
<article>
  <h1>Gestion des dépenses d'entreprise: Guide complet pour les responsables financiers</h1>
  <p>La gestion des dépenses d'entreprise est le processus de suivi, d'approbation et de déclaration des dépenses professionnelles engagées par les employés de l'organisation.</p>
  <p>Selon une étude de 2024, les entreprises qui automatisent la gestion des dépenses économisent en moyenne 65% sur les coûts de traitement des notes de frais et des remboursements.</p>
</article>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests: Backward Compatibility
# ---------------------------------------------------------------------------
class TestBackwardCompatibility:
    """Existing JSON with only original 11 fields should still load."""

    def test_old_signals_json_loads(self):
        """StructuralSignals(**old_dict) should work — new fields get defaults."""
        old_data = {
            "word_count": 500,
            "paragraph_count": 10,
            "header_count": 3,
            "list_item_count": 5,
            "stat_count": 2,
            "citation_count": 4,
            "has_headers": True,
            "has_lists": True,
            "has_numbers": True,
            "authority_type": "commercial_or_media",
            "content_type": "blog_or_article",
        }
        signals = StructuralSignals(**old_data)
        assert signals.word_count == 500
        # New fields should have defaults
        assert signals.h1_count == 0
        assert signals.has_faq_section is False
        assert signals.reading_level == 0.0
        assert signals.per_paragraph_word_counts == []


# ---------------------------------------------------------------------------
# Tests: Category A — Text Composition
# ---------------------------------------------------------------------------
class TestTextComposition:
    """Tests for Category A: text composition signals."""

    def test_sentence_and_paragraph_metrics(self):
        """Should compute sentence count, avg/median paragraph length, max paragraph word count."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        paragraphs, signals = _extract_paragraphs(RICH_ARTICLE_HTML)

        assert signals.sentence_count > 0
        assert signals.avg_paragraph_length > 0
        assert signals.median_paragraph_length > 0
        assert signals.max_paragraph_word_count > 0
        assert signals.avg_sentence_length > 0
        assert signals.avg_sentence_count_per_paragraph > 0
        assert len(signals.per_paragraph_word_counts) == signals.paragraph_count

    def test_reading_level_computed(self):
        """Should compute a Flesch-Kincaid reading level for English content."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)

        # Flesch-Kincaid typically returns 8-16 for professional content
        assert signals.reading_level > 0.0, "Reading level should be computed for English content"

    def test_self_contained_ratio(self):
        """Self-contained ratio should be between 0 and 1."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert 0.0 <= signals.self_contained_ratio <= 1.0


# ---------------------------------------------------------------------------
# Tests: Category B — Structural Elements
# ---------------------------------------------------------------------------
class TestStructuralElements:
    """Tests for Category B: per-level header counts, list types, tables, code blocks."""

    def test_per_header_level_counts(self):
        """Should count h1, h2, h3, h4 separately."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)

        assert signals.h1_count >= 1
        assert signals.h2_count >= 2
        assert signals.h3_count >= 1
        # Total should match or exceed header_count
        per_level_total = signals.h1_count + signals.h2_count + signals.h3_count + signals.h4_count
        assert per_level_total == signals.header_count

    def test_list_type_counts(self):
        """Should distinguish ordered vs unordered lists."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)

        assert signals.unordered_list_count >= 1  # <ul> in key takeaways
        assert signals.ordered_list_count >= 1  # <ol> in step-by-step
        assert signals.list_block_count >= 2  # at least 2 list blocks
        assert signals.bullets_per_list_block > 0

    def test_table_and_blockquote_detection(self):
        """Should detect tables and blockquotes."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)

        assert signals.table_count >= 1
        assert signals.blockquote_count >= 1

    def test_code_block_detection(self):
        """Should detect <pre><code> blocks."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(CODE_BLOCK_HTML)

        assert signals.code_block_count >= 1


# ---------------------------------------------------------------------------
# Tests: Category C — Content Patterns
# ---------------------------------------------------------------------------
class TestContentPatterns:
    """Tests for Category C: FAQ, step-by-step, key takeaways detection."""

    def test_faq_detection(self):
        """Should detect FAQ sections via headings or <details>/<dl> elements."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.has_faq_section is True

    def test_step_by_step_detection(self):
        """Should detect step-by-step content from ordered lists or step-like headings."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.has_step_by_step is True

    def test_key_takeaways_detection(self):
        """Should detect key takeaways / summary sections."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.has_key_takeaways is True

    def test_expert_quotes_detection(self):
        """Should detect expert quotes from blockquote elements with attribution patterns."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.has_expert_quotes is True

    def test_definition_list_detection(self):
        """Should detect FAQ-like <dl> patterns."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(FAQ_HTML)
        assert signals.definition_list_count >= 1


# ---------------------------------------------------------------------------
# Tests: Category D — Factual Density
# ---------------------------------------------------------------------------
class TestFactualDensity:
    """Tests for Category D: data points, citation density, entity density."""

    def test_data_point_detection(self):
        """Should detect percentages, dollar amounts, and numeric data points."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.data_point_count > 0

    def test_citation_density(self):
        """Citation density = links per 1000 words."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.citation_density >= 0.0

    def test_research_refs_detection(self):
        """Should detect 'according to' and research attribution patterns."""
        from core.gap_analysis.steps.s4_enrich_citations import _extract_paragraphs

        _, signals = _extract_paragraphs(RICH_ARTICLE_HTML)
        assert signals.has_research_refs is True
