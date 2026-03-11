"""DB persistence hooks for the Site Audit pipeline.

After the pipeline writes ``audit_result.json`` to the filesystem, the runner
optionally calls :func:`persist_site_audit_result` to write the full audit
result into Postgres via :class:`SiteAuditRepository`.

Design principles (mirrors ``core/research/persistence.py``):
- **Filesystem-first, DB-additive**: JSON always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.
- **Status mapping**: Pipeline ``"degraded"`` → ``PipelineStatus.completed``
  + ``is_degraded=True``.  A degraded audit IS completed; the
  ``failed_steps`` / ``degraded_dimensions`` arrays capture the details.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


# ── Guard ────────────────────────────────────────────────────────────────


def _should_persist(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
) -> bool:
    """Return True if DB persistence is configured."""
    return (
        session_factory is not None
        and run_id is not None
        and company_id is not None
    )


# ── Status mapping ───────────────────────────────────────────────────────


def _map_status(pipeline_status: str) -> tuple:
    """Map pipeline status string to (PipelineStatus, is_degraded).

    ``"degraded"`` is not a valid PipelineStatus enum value, so we map it
    to ``completed`` and set ``is_degraded=True``.
    """
    from core.db.enums import PipelineStatus

    if pipeline_status == "degraded":
        return PipelineStatus.completed, True
    if pipeline_status == "failed":
        return PipelineStatus.failed, False
    if pipeline_status == "running":
        return PipelineStatus.running, False
    if pipeline_status == "pending":
        return PipelineStatus.pending, False
    # Default: completed
    return PipelineStatus.completed, False


# ── Finding dedup ────────────────────────────────────────────────────────


def _dedup_findings(
    page_findings: list[dict[str, Any]],
    top_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge page findings and top_findings, deduplicating by (url, finding_type, dimension)."""
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []

    for f in page_findings:
        key = (f.get("url", ""), f.get("finding_type", ""), f.get("dimension", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    for f in top_findings:
        key = (f.get("url", ""), f.get("finding_type", ""), f.get("dimension", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    return deduped


# ── Main persistence function ────────────────────────────────────────────


async def persist_site_audit_result(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    audit_result: Any,
    *,
    pipeline_run_id: Optional[_uuid.UUID] = None,
) -> None:
    """Persist a SiteAuditResult to the database.

    Creates a ``SiteAuditModel`` row with all enriched columns, then bulk
    inserts ``AuditFindingModel`` and ``AuditPageResultModel`` rows.

    Args:
        session_factory: Async session factory (None = skip persistence).
        run_id: Pipeline run UUID.
        company_id: Company UUID.
        effective_slug: Effective slug for artifact scoping.
        audit_result: The ``SiteAuditResult`` Pydantic model.
        pipeline_run_id: Optional FK to ``pipeline_runs`` table.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None and company_id is not None

    try:
        from core.db.enums import FindingSeverity
        from core.db.repositories.site_audit_repo import SiteAuditRepository

        # Parse audit_id as UUID, generate new one if invalid
        try:
            audit_uuid = _uuid.UUID(audit_result.audit_id)
        except (ValueError, AttributeError):
            audit_uuid = _uuid.uuid4()

        # Map status
        db_status, is_degraded = _map_status(audit_result.status)

        async with session_factory() as session:
            repo = SiteAuditRepository(session)

            # 1. Create SiteAuditModel row
            await repo.create(
                id=audit_uuid,
                company_id=company_id,
                site_domain=audit_result.domain,
                status=db_status,
                is_degraded=is_degraded,
                effective_slug=effective_slug,
                pipeline_run_id=pipeline_run_id,
                overall_score=audit_result.overall_score,
                grade=audit_result.grade,
                pages_crawled=audit_result.pages_crawled,
                pages_discovered=audit_result.pages_discovered,
                duration_seconds=audit_result.duration_seconds,
                started_at=audit_result.started_at,
                completed_at=audit_result.completed_at,
                findings_count=audit_result.total_findings,
                dimension_scores=[
                    ds.model_dump(mode="json")
                    for ds in audit_result.dimension_scores
                ],
                ai_bot_access=(
                    audit_result.ai_bot_access.model_dump(mode="json")
                    if audit_result.ai_bot_access
                    else None
                ),
                sitemap_health=(
                    audit_result.sitemap_health.model_dump(mode="json")
                    if audit_result.sitemap_health
                    else None
                ),
                findings_by_severity=audit_result.findings_by_severity,
                findings_by_dimension=audit_result.findings_by_dimension,
                top_findings=audit_result.top_findings,
                avg_snippet_readiness=audit_result.avg_snippet_readiness,
                pages_with_schema=audit_result.pages_with_schema,
                avg_question_heading_ratio=audit_result.avg_question_heading_ratio,
                error_message=audit_result.error_message,
                failed_steps=audit_result.failed_steps or None,
                degraded_dimensions=audit_result.degraded_dimensions or None,
            )

            # 2. Flatten findings from page_results
            page_findings: list[dict[str, Any]] = []
            for page in audit_result.page_results:
                for f in page.findings:
                    sev_val = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                    dim_val = f.dimension.value if hasattr(f.dimension, "value") else str(f.dimension)
                    try:
                        sev_enum = FindingSeverity(sev_val)
                    except (ValueError, KeyError):
                        sev_enum = FindingSeverity.info
                    page_findings.append({
                        "page_url": f.url or page.url,
                        "finding_type": f.finding_type,
                        "dimension": dim_val,
                        "severity": sev_enum,
                        "message": f.message,
                        "recommendation": f.recommendation,
                        "details": f.details if f.details else None,
                    })

            # Normalize top_findings (list of dicts) for dedup
            top_findings_normalized: list[dict[str, Any]] = []
            for tf in (audit_result.top_findings or []):
                if isinstance(tf, dict):
                    dim_val = tf.get("dimension", "")
                    if hasattr(dim_val, "value"):
                        dim_val = dim_val.value
                    top_findings_normalized.append({
                        "page_url": tf.get("url", ""),
                        "finding_type": tf.get("finding_type", ""),
                        "dimension": str(dim_val),
                        "severity": tf.get("severity", "info"),
                        "message": tf.get("message", ""),
                        "recommendation": tf.get("recommendation", ""),
                        "details": tf.get("details"),
                        "url": tf.get("url", ""),
                    })

            # Dedup: use url key from page_findings (stored in page_url)
            dedup_page = [
                {**f, "url": f["page_url"]}
                for f in page_findings
            ]
            dedup_top = [
                {**f, "url": f.get("url", f.get("page_url", ""))}
                for f in top_findings_normalized
            ]
            deduped = _dedup_findings(dedup_page, dedup_top)

            # Convert back: map severity strings from top_findings to enums
            final_findings: list[dict[str, Any]] = []
            for f in deduped:
                sev = f.get("severity")
                if isinstance(sev, str):
                    try:
                        sev = FindingSeverity(sev)
                    except (ValueError, KeyError):
                        sev = FindingSeverity.info
                final_findings.append({
                    "page_url": f.get("page_url", f.get("url", "")),
                    "finding_type": f.get("finding_type", ""),
                    "dimension": f.get("dimension", ""),
                    "severity": sev,
                    "message": f.get("message", ""),
                    "recommendation": f.get("recommendation", ""),
                    "details": f.get("details"),
                })

            # Batch insert findings
            await repo.bulk_insert_findings(audit_uuid, final_findings)

            # 3. Build page result dicts
            page_result_dicts: list[dict[str, Any]] = []
            for idx, page in enumerate(audit_result.page_results):
                schema_result = getattr(page, "schema_result", None)
                aeo = getattr(page, "aeo", None)
                page_result_dicts.append({
                    "page_index": idx,
                    "url": page.url,
                    "status_code": page.status_code,
                    "crawl_depth": getattr(page, "crawl_depth", None),
                    "title": getattr(page, "title", None),
                    "word_count": getattr(page, "word_count", None),
                    "reading_level": getattr(page, "reading_level", None),
                    "has_schema": (
                        schema_result.has_schema
                        if schema_result and hasattr(schema_result, "has_schema")
                        else None
                    ),
                    "snippet_readiness_score": (
                        aeo.snippet_readiness_score
                        if aeo and hasattr(aeo, "snippet_readiness_score")
                        else None
                    ),
                    "finding_count": len(page.findings),
                    "has_https": getattr(page, "has_https", None),
                    "is_noindex": getattr(page, "is_noindex", None),
                    "result_json": page.model_dump(mode="json"),
                })

            # Batch insert page results
            await repo.bulk_insert_page_results(audit_uuid, page_result_dicts)

            await session.commit()

        logger.info(
            "persist_site_audit_result: audit %s stored for %s "
            "(score=%.1f, grade=%s, %d findings, %d pages)",
            audit_uuid, effective_slug,
            audit_result.overall_score, audit_result.grade,
            len(final_findings), len(page_result_dicts),
        )

    except Exception:
        logger.warning(
            "persist_site_audit_result failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )
