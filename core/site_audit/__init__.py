"""Site Audit Pipeline (Pipeline 0).

Diagnoses how AI-ready a website is by auditing 8 dimensions:
crawlability, performance, on_page_seo, extractability (AEO),
schema_markup, eeat, freshness, security.

All checks are deterministic — no LLM calls.

Public surface::

    from core.site_audit.pipeline import run_site_audit
    from core.site_audit.config import DEFAULT_AUDIT_CONFIG, AuditConfig
    from core.models.site_audit import SiteAuditInput, SiteAuditResult
"""
from __future__ import annotations
