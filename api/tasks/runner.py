"""Background task wrappers for pipeline execution."""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from api.tasks.event_bus import EventBus
from api.tasks.models import TaskStatus
from core.services.task_store import TaskStoreProtocol
from core.gap_analysis.pipeline import run_gap_analysis
from core.auth.utils.domain import derive_slug
from core.models.gap_analysis import GapAnalysisInput
from core.shared_tools.structured_logging import bind_context, clear_context

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


# ── Scope resolution ──────────────────────────────────────────────────


@dataclass
class RunScope:
    """Resolved scope for a single pipeline run."""

    company_slug: str
    product_slug: Optional[str]
    effective_slug: str  # artifact dirs + lock key
    product_name: Optional[str]
    product_description: Optional[str]
    product_domain: Optional[str]


def _resolve_scope(
    company_slug: str,
    product_slug: Optional[str],
    auth_store: Optional[Any] = None,
) -> RunScope:
    """Resolve a RunScope from company_slug + product_slug.

    Looks up product details from auth_store when product_slug is set.
    Sync version — kept for CLI compatibility.
    """
    effective = f"{company_slug}__{product_slug}" if product_slug else company_slug
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_domain: Optional[str] = None

    if product_slug and auth_store:
        product = auth_store.get_product(company_slug, product_slug)
        if product:
            product_name = product.name
            product_description = product.description
            product_domain = product.domain

    return RunScope(
        company_slug=company_slug,
        product_slug=product_slug,
        effective_slug=effective,
        product_name=product_name,
        product_description=product_description,
        product_domain=product_domain,
    )


async def _resolve_scope_async(
    company_slug: str,
    product_slug: Optional[str],
    auth_service: Optional[Any] = None,
) -> RunScope:
    """Async version of _resolve_scope using AuthServiceProtocol."""
    effective = f"{company_slug}__{product_slug}" if product_slug else company_slug
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_domain: Optional[str] = None

    if product_slug and auth_service:
        product = await auth_service.get_product(company_slug, product_slug)
        if product:
            product_name = product.name
            product_description = product.description
            product_domain = product.domain

    return RunScope(
        company_slug=company_slug,
        product_slug=product_slug,
        effective_slug=effective,
        product_name=product_name,
        product_description=product_description,
        product_domain=product_domain,
    )


def _derive_slug(company_name: str, company_slug: Optional[str] = None) -> str:
    if company_slug:
        return company_slug
    return derive_slug(company_name) or company_name.lower()


def resolve_artifacts(
    slug: str,
    artifacts_root: Path,
    effective_slug: Optional[str] = None,
    *,
    backend: Optional[Any] = None,
) -> Dict[str, Any]:
    """Auto-discover approved research artifacts for a company slug.

    Only resolves final (approved) artifacts — ignores .draft.md files.
    When backend is LocalStorageBackend, returns absolute filesystem paths
    for backward compatibility with downstream consumers.
    """
    from core.storage.backends.local import LocalStorageBackend
    _backend = backend or LocalStorageBackend(artifacts_root)

    resolved: Dict[str, Any] = {
        "company_context_path": None,
        "persona_paths": [],
        "style_guide_path": None,
    }
    candidates = [effective_slug, slug] if effective_slug and effective_slug != slug else [slug]

    # Company context
    for lookup in candidates:
        key = f"company_context/{lookup}.md"
        if _backend.exists(key):
            if isinstance(_backend, LocalStorageBackend):
                resolved["company_context_path"] = str(_backend.root / key)
            else:
                resolved["company_context_path"] = key
            break

    # Personas: via PersonaStorage (no legacy fallback)
    for lookup in candidates:
        try:
            from core.research.audience_persona.storage import PersonaStorage
            ap_storage = PersonaStorage(artifacts_root, lookup, backend=_backend)
            ap_paths = ap_storage.list_persona_paths()
            if ap_paths:
                resolved["persona_paths"] = ap_paths
                break
        except Exception:
            pass

    # Style guide
    for lookup in candidates:
        key = f"style_guides/{lookup}.md"
        if _backend.exists(key):
            if isinstance(_backend, LocalStorageBackend):
                resolved["style_guide_path"] = str(_backend.root / key)
            else:
                resolved["style_guide_path"] = key
            break

    return resolved


async def _resolve_db_context(
    company_slug: str,
    effective_slug: str,
) -> tuple[Optional[async_sessionmaker], Optional[uuid.UUID], Optional[uuid.UUID]]:
    """Resolve session_factory, run_id, and company_id for DB persistence.

    Returns (None, None, None) if DATABASE_URL is not set or company not in DB.
    Never raises — all failures are logged and result in disabled DB writes.
    """
    try:
        from core.config.settings import settings

        if not settings.database_url:
            return None, None, None

        from core.db.engine import get_session_factory
        from core.db.repositories.company_repo import CompanyRepository

        sf = get_session_factory()
        run_id = uuid.uuid4()

        async with sf() as session:
            repo = CompanyRepository(session)
            company = await repo.get_by_slug(company_slug)
            if company is None:
                logger.warning(
                    "Company '%s' not found in DB — skipping DB persistence",
                    company_slug,
                )
                return None, None, None
            company_id = company.id

        return sf, run_id, company_id
    except Exception:
        logger.warning("DB context resolution failed — continuing without DB", exc_info=True)
        return None, None, None


async def _create_pipeline_run(
    session_factory: async_sessionmaker,
    run_id: uuid.UUID,
    company_id: uuid.UUID,
    effective_slug: str,
    pipeline_type_str: str,
) -> None:
    """Create a PipelineRunModel record in the DB."""
    try:
        from core.db.enums import PipelineStatus, PipelineType
        from core.db.models.pipelines import PipelineRunModel

        pipeline_type = PipelineType(pipeline_type_str)
        async with session_factory() as session:
            run = PipelineRunModel(
                id=run_id,
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_type=pipeline_type,
                status=PipelineStatus.running,
                started_at=datetime.now(tz=timezone.utc),
            )
            session.add(run)
            await session.commit()
    except Exception:
        logger.warning("Failed to create PipelineRunModel — continuing", exc_info=True)


async def _mark_pipeline_run_complete(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[uuid.UUID],
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark a PipelineRunModel as completed (idempotent).

    Safe to call even if the pipeline already called persist_pipeline_run_complete
    internally — the first write wins (status check).
    """
    if session_factory is None or run_id is None:
        return
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run and run.status != PipelineStatus.completed:
                run.status = PipelineStatus.completed
                run.completed_at = datetime.now(tz=timezone.utc)
                if summary:
                    run.summary = summary
                await session.commit()
    except Exception:
        logger.warning("Failed to mark PipelineRunModel as completed", exc_info=True)


async def _mark_pipeline_run_failed(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[uuid.UUID],
    error: str,
) -> None:
    """Mark a PipelineRunModel as failed."""
    if session_factory is None or run_id is None:
        return
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run:
                run.status = PipelineStatus.failed
                run.error_message = error[:2000] if error else None
                run.completed_at = datetime.now(tz=timezone.utc)
                await session.commit()
    except Exception:
        logger.warning("Failed to mark PipelineRunModel as failed", exc_info=True)


def _cleanup_stale_pipeline_state(
    artifacts_root: Optional[Path], effective_slug: str,
) -> None:
    """Best-effort removal of pipeline_state.json on failure/cancel.

    On error paths we cannot determine which brief IDs belong to this run
    (pieces may be empty), so we remove the whole file. This is acceptable
    because parallel runs are manual-mode only (no HITL-1/2 state to
    preserve), and file-based inference (Phase 2) still works correctly.
    """
    if not artifacts_root:
        return
    state_path = artifacts_root / "content" / effective_slug / "pipeline_state.json"
    if state_path.is_file():
        try:
            state_path.unlink()
        except OSError:
            pass


async def run_gap_pipeline_task(
    task_id: str,
    request: Any,
    artifacts_root: Path,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
    """Background task wrapper for gap analysis pipeline.

    Accepts the simplified GapAnalysisStartRequest, auto-resolves research
    artifact paths from disk, and constructs GapAnalysisInput internally.
    """
    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Resolve DB context for Phase 4 persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "gap_analysis",
        )

    bind_context(task_id=task_id, pipeline_name="gap_analysis", company_slug=scope.company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "gap_analysis"})

            # C1-fix: create configured backend BEFORE resolve_artifacts
            # so artifact resolution uses R2 in production (not hardcoded local)
            from core.storage import get_storage_backend
            _storage = get_storage_backend(artifacts_root)

            # Research artifacts: fallback chain (product-specific → company-level)
            resolved = resolve_artifacts(
                scope.company_slug,
                artifacts_root,
                effective_slug=scope.effective_slug,
                backend=_storage,
            )

            # S1 domain: use product domain when available (D4 — Replace strategy)
            domain = request.domain
            if scope.product_domain:
                domain = scope.product_domain

            # Knowledge docs: product-level → company-level fallback (via StorageBackend)
            knowledge_doc_slug: Optional[str] = None
            for candidate_slug in [scope.effective_slug, scope.company_slug]:
                if _storage.exists(f"knowledge_docs/{candidate_slug}/_metadata.json"):
                    knowledge_doc_slug = candidate_slug
                    break

            # Merge company pipeline defaults for Optional fields: request
            # values take precedence, then company defaults.  Non-optional
            # request fields (max_queries, platforms) are always present so
            # they pass through directly.
            _defaults = (await auth_service.get_pipeline_defaults(scope.company_slug)) if auth_service else None

            input_data = GapAnalysisInput(
                company_name=request.company_name,
                domain=domain,
                company_slug=scope.effective_slug,  # artifact dir uses effective slug
                seed_urls=request.seed_urls or [f"https://{domain}/"],
                company_context_path=resolved["company_context_path"],
                persona_paths=resolved["persona_paths"],
                max_queries=request.max_queries,
                platforms=request.platforms,
                language=request.language,
                region=request.region,
                additional_constraints=request.additional_constraints,
                max_crawl_pages=(
                    request.max_crawl_pages
                    or (_defaults.max_crawl_pages if _defaults else None)
                ),
                max_crawl_depth=(
                    request.max_crawl_depth
                    or (_defaults.max_crawl_depth if _defaults else None)
                ),
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                product_description=scope.product_description,
                knowledge_doc_slug=knowledge_doc_slug,
            )

            report = await run_gap_analysis(
                input_data=input_data,
                skip_steps=request.skip_steps,
                storage=_storage,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )
            result = {
                "report_md": report.report_md or None,
                "report_json": report.report_json,
                "visualization_paths": report.visualization_paths,
                "resolved_artifacts": resolved,
                "produced_artifacts": [
                    {"type": "gap_analysis", "slug": scope.effective_slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result
            )
            event_bus.publish(task_id, "completed", {"pipeline": "gap_analysis"})
    except asyncio.CancelledError:
        logger.info("Gap analysis pipeline cancelled: task_id=%s", task_id)
        # Status already set by cancel endpoint; just ensure slug lock released
    except Exception as exc:
        logger.exception("Gap analysis pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc)
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"gap_analysis:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ── Research pipeline runner ─────────────────────────────────────────


# ── Content generation pipeline runner ───────────────────────────────


async def run_site_audit_task(
    task_id: str,
    request: Any,
    artifacts_root: Path,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
    """Background task wrapper for site audit pipeline.

    Derives slugs from the request, emits SSE events, calls the site audit
    pipeline (when implemented), persists results, and updates the task store.
    All exceptions are caught so the background task never crashes silently.

    Args:
        task_id: The task UUID created by the router.
        request: SiteAuditStartRequest with company_name, domain, and options.
        artifacts_root: Filesystem root for artifact persistence.
        task_store: Task persistence store.
        event_bus: SSE event bus for real-time progress streaming.
        auth_service: Optional auth service for product lookups.
    """
    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Initialise DB vars before try so they're always available in finally
    session_factory: Any = None
    run_id: Any = None
    company_id: Any = None

    bind_context(task_id=task_id, pipeline_name="site_audit", company_slug=scope.company_slug)
    try:
        # Resolve DB context for site audit persistence
        session_factory, run_id, company_id = await _resolve_db_context(
            scope.company_slug, scope.effective_slug,
        )
        if session_factory and run_id and company_id:
            await _create_pipeline_run(
                session_factory, run_id, company_id,
                scope.effective_slug, "site_audit",
            )
        if run_id:
            bind_context(run_id=str(run_id))

        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "site_audit"})

            try:
                from core.site_audit.pipeline import run_site_audit
                from core.models.site_audit import SiteAuditInput

                input_data = SiteAuditInput(
                    company_name=request.company_name,
                    domain=request.domain,
                    company_slug=scope.effective_slug,
                    product_slug=scope.product_slug,
                    max_pages=getattr(request, "max_pages", 200),
                    max_depth=getattr(request, "max_depth", 4),
                    check_core_web_vitals=getattr(request, "check_core_web_vitals", True),
                    check_schema_validation=getattr(request, "check_schema_validation", True),
                    check_ai_bot_access=getattr(request, "check_ai_bot_access", True),
                )

                audit_result = await run_site_audit(input_data)

                # 1. Persist audit_result.json (filesystem-first)
                out_dir = (
                    artifacts_root
                    / "site_audit"
                    / scope.effective_slug
                    / audit_result.audit_id
                )
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "audit_result.json").write_text(
                    audit_result.model_dump_json(indent=2), encoding="utf-8"
                )

                # 2. Persist to DB (additive — never crashes pipeline)
                from core.site_audit.persistence import persist_site_audit_result

                await persist_site_audit_result(
                    session_factory, run_id, company_id,
                    scope.effective_slug, audit_result,
                    pipeline_run_id=run_id,
                )

                result = {
                    "audit_id": audit_result.audit_id,
                    "domain": audit_result.domain,
                    "overall_score": audit_result.overall_score,
                    "grade": audit_result.grade,
                    "pages_crawled": audit_result.pages_crawled,
                    "status": audit_result.status,
                    "produced_artifacts": [
                        {"type": "site_audit", "slug": scope.effective_slug},
                    ],
                }

                # Propagate degraded pipeline info into task result
                if audit_result.status == "degraded":
                    result["degraded"] = True
                    result["failed_steps"] = audit_result.failed_steps
                    result["degraded_dimensions"] = audit_result.degraded_dimensions
            except (ImportError, NotImplementedError):
                # Pipeline not yet wired — record a placeholder result
                logger.warning(
                    "run_site_audit not available (pipeline not yet implemented): task_id=%s",
                    task_id,
                )
                result = {
                    "audit_id": "",
                    "domain": request.domain,
                    "status": "not_implemented",
                    "produced_artifacts": [],
                }

            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result
            )
            event_bus.publish(task_id, "completed", {"pipeline": "site_audit"})

            # 3. Mark pipeline run complete in DB
            await _mark_pipeline_run_complete(session_factory, run_id, summary={
                "audit_id": result.get("audit_id", ""),
                "overall_score": result.get("overall_score"),
                "grade": result.get("grade"),
            })

    except asyncio.CancelledError:
        logger.info("Site audit pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Site audit pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc)
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"site_audit:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_content_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for content generation pipeline.

    Passes task_store and event_bus through to run_content_generation() so
    Stage 4 can use HITL interrupt/resume when auto_approve is False.
    """
    from core.content_engine.pipeline import run_content_generation

    # Read effective_slug from the persisted task (set by create_task at launch)
    _task = task_store.get_task(task_id)
    effective = _task.effective_slug or _task.company_slug or _derive_slug(input_data.company_name)
    company_slug = _task.company_slug or _derive_slug(input_data.company_name)

    # Resolve DB context for Phase 4 persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        company_slug, effective
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            effective, "content",
        )

    bind_context(task_id=task_id, pipeline_name="content", company_slug=company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content"})

            output = await run_content_generation(
                input_data=input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            result = {
                "company_slug": output.company_slug,
                "total_briefs": output.total_briefs,
                "total_approved": output.total_approved,
                "total_rejected": output.total_rejected,
                "pieces": [
                    {
                        "brief_id": p.brief_id,
                        "title": p.title,
                        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                    }
                    for p in output.pieces
                ],
                "produced_artifacts": [
                    {"type": "content", "slug": effective},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result
            )
            event_bus.publish(task_id, "completed", {"pipeline": "content"})

    except asyncio.CancelledError:
        logger.info("Content generation pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Content generation pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"content:{effective}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_content_v13_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    artifacts_root: Optional[Path] = None,
    *,
    is_parallel: bool = False,
) -> None:
    """Background task wrapper for v1.3 content generation pipeline.

    Follows the same semaphore + slug-lock + handle pattern as
    run_content_pipeline_task. Enforces the global max-3-concurrent
    semaphore and registers the task handle for cancellation.

    Args:
        is_parallel: If True, the task was created without a slug lock
            (manual mode parallel runs). Skip lock release in finally.
    """
    from core.content_engine.pipeline_v13 import run_content_generation_v13

    _task = task_store.get_task(task_id)
    effective = _task.effective_slug or _task.company_slug or _derive_slug(input_data.company_name)
    company_slug = _task.company_slug or _derive_slug(input_data.company_name)

    # C1-fix: use configured backend for artifact resolution (R2 in prod)
    if artifacts_root:
        from core.storage import get_storage_backend
        _storage = get_storage_backend(artifacts_root)
        resolved = resolve_artifacts(company_slug, artifacts_root, effective_slug=effective, backend=_storage)
        if resolved["company_context_path"]:
            input_data.company_context_path = resolved["company_context_path"]
        if resolved["style_guide_path"]:
            input_data.style_guide_path = resolved["style_guide_path"]
        if resolved["persona_paths"]:
            input_data.persona_paths = resolved["persona_paths"]

    session_factory, run_id, company_id = await _resolve_db_context(company_slug, effective)
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id, effective, "content"
        )

    bind_context(task_id=task_id, pipeline_name="content_v13", company_slug=company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content_v13"})

            output = await run_content_generation_v13(
                input_data=input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            result = {
                "company_slug": output.company_slug,
                "total_briefs": output.total_briefs,
                "total_approved": output.total_approved,
                "total_rejected": output.total_rejected,
                "pieces": [
                    {
                        "brief_id": p.brief_id,
                        "title": p.title,
                        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                    }
                    for p in output.pieces
                ],
                "produced_artifacts": [{"type": "content_v13", "slug": effective}],
            }
            task_store.update_task(task_id, status=TaskStatus.COMPLETED, result=result)
            event_bus.publish(task_id, "completed", {"pipeline": "content_v13"})

    except asyncio.CancelledError:
        logger.info("Content v1.3 pipeline cancelled: task_id=%s", task_id)
        _cleanup_stale_pipeline_state(artifacts_root, effective)
    except Exception as exc:
        logger.exception("Content v1.3 pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
        _cleanup_stale_pipeline_state(artifacts_root, effective)
    finally:
        if not is_parallel:
            task_store.release_slug_lock(f"content_v13:{effective}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ── Knowledge Base pipeline runner ─────────────────────────────────


async def run_kb_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
    """Background task wrapper for Knowledge Base pipeline.

    Acquires task_store semaphore, resolves scope, calls
    run_knowledge_base_pipeline(), and handles completion/failure/cancellation.
    """
    from core.models.knowledge_base import KnowledgeBaseInput
    from core.research.knowledge_base.pipeline import run_knowledge_base_pipeline

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Resolve DB context for research artifact persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "knowledge_base",
        )

    bind_context(task_id=task_id, pipeline_name="knowledge_base", company_slug=scope.company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            input_data = KnowledgeBaseInput(
                company_name=request.company_name,
                domain=getattr(request, "domain", None),
                company_slug=scope.effective_slug,
                company_id=getattr(request, "company_id", None),
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                seed_urls=getattr(request, "seed_urls", []),
                internal_sources=getattr(request, "internal_sources", []),
                language=getattr(request, "language", "en"),
                region=getattr(request, "region", None),
                additional_constraints=getattr(request, "additional_constraints", None),
                refresh_docs=getattr(request, "refresh_docs", None),
                staleness_threshold_days=getattr(request, "staleness_threshold_days", 30),
                auto_approve_checkpoints=getattr(request, "auto_approve_checkpoints", []),
                express_mode=getattr(request, "express_mode", False),
            )

            output = await run_knowledge_base_pipeline(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            # Ensure pipeline run is marked complete (idempotent)
            await _mark_pipeline_run_complete(session_factory, run_id)

            result = {
                "slug": output.slug,
                "company_name": output.company_name,
                "synthesis_word_count": len(output.synthesis_md.split()) if output.synthesis_md else 0,
                "agent_results": {
                    k: {
                        "word_count": v.word_count,
                        "has_error": v.error is not None,
                        "error": v.error,
                    }
                    for k, v in output.agent_results.items()
                },
                "company_profile_path": output.company_profile_path,
                "produced_artifacts": [
                    {"type": "knowledge_base", "slug": scope.effective_slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result,
            )

    except asyncio.CancelledError:
        logger.info("KB pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("KB pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"knowledge_base:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ═══════════════════════════════════════════════════════════════════════
# Audience Persona Pipeline
# ═══════════════════════════════════════════════════════════════════════


async def run_audience_persona_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> None:
    """Background task wrapper for Audience Persona pipeline."""
    from core.models.audience_persona import AudiencePersonaInput
    from core.research.audience_persona.pipeline import run_audience_persona_pipeline

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Resolve DB context for research artifact persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "audience_persona",
        )

    bind_context(task_id=task_id, pipeline_name="audience_persona", company_slug=scope.company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            input_data = AudiencePersonaInput(
                company_name=request.company_name,
                domain=getattr(request, "domain", None),
                company_slug=scope.company_slug,
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                max_personas=getattr(request, "max_personas", 5),
                language=getattr(request, "language", "en"),
                region=getattr(request, "region", None),
                additional_constraints=getattr(request, "additional_constraints", None),
                auto_approve_checkpoints=getattr(request, "auto_approve_checkpoints", []),
            )

            output = await run_audience_persona_pipeline(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                artifacts_root=artifacts_root,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            # Ensure pipeline run is marked complete (idempotent)
            await _mark_pipeline_run_complete(session_factory, run_id)

            result = {
                "slug": output.slug,
                "company_name": output.company_name,
                "briefs_suggested": output.briefs_suggested,
                "briefs_approved": output.briefs_approved,
                "profiles_generated": output.profiles_generated,
                "persona_dir": output.persona_dir,
                "produced_artifacts": [
                    {"type": "audience_persona", "slug": scope.effective_slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result,
            )

    except asyncio.CancelledError:
        logger.info("AP pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("AP pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"audience_persona:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_single_persona_generator_task(
    task_id: str,
    persona_id: str,
    slug: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    artifacts_root: Any = None,
) -> None:
    """Background task for standalone single-persona generation."""
    from core.models.audience_persona import AudiencePersonaInput
    from core.research.audience_persona.agents import run_persona_profile_generator
    from core.research.audience_persona.pipeline import _preflight_check
    from core.research.audience_persona.storage import PersonaStorage

    bind_context(task_id=task_id, pipeline_name="audience_persona", company_slug=slug)
    try:
        async with task_store.semaphore:
            root = Path(artifacts_root) if artifacts_root else Path("artifacts")
            storage = PersonaStorage(root, slug)
            brief = storage.read_brief(persona_id)

            if not brief:
                raise ValueError(f"No brief found for persona_id={persona_id}")

            # Derive base company slug (strip product suffix if present)
            company_slug = slug.split("__")[0]

            # Load context via preflight (effective_slug=slug for standalone)
            company_md, reviews_md, kdocs_text, _ = await _preflight_check(
                root, slug, company_slug,
            )

            # Build minimal input_data for the generator prompt
            manifest = storage.read_manifest()
            input_data = AudiencePersonaInput(
                company_name=manifest.company_name or company_slug,
                company_slug=company_slug,
                product_slug=slug.split("__")[1] if "__" in slug else None,
            )

            result = await run_persona_profile_generator(
                brief=brief,
                input_data=input_data,
                company_context_md=company_md,
                customer_reviews_md=reviews_md,
                knowledge_docs_text=kdocs_text,
            )

            if result.error:
                raise RuntimeError(f"Profile generation failed: {result.error}")

            storage.write_version(
                persona_id,
                persona_name=brief.persona_name,
                content_md=result.content_md,
                content_json=result.content_json,
                kind="secondary",
                created_by="manual",
                tagline=brief.tagline,
                status="pending_review",
            )

            task_store.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result={"persona_id": persona_id, "status": "pending_review"},
            )

    except asyncio.CancelledError:
        logger.info("Single persona gen cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Single persona gen failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(f"audience_persona:{slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ---------------------------------------------------------------------------
# Voice Style Guide Pipeline
# ---------------------------------------------------------------------------


async def run_voice_style_guide_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> None:
    """Background task wrapper for Voice Style Guide pipeline."""
    from core.models.voice_style_guide import VoiceStyleGuideInput
    from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Resolve DB context for research artifact persistence
    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "voice_style_guide",
        )

    bind_context(task_id=task_id, pipeline_name="voice_style_guide", company_slug=scope.company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            input_data = VoiceStyleGuideInput(
                company_name=request.company_name,
                domain=getattr(request, "domain", None),
                company_slug=scope.company_slug,
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                max_authors=getattr(request, "max_authors", 3),
                language=getattr(request, "language", "en"),
                region=getattr(request, "region", None),
                additional_constraints=getattr(request, "additional_constraints", None),
                auto_approve_checkpoints=getattr(request, "auto_approve_checkpoints", []),
            )

            output = await run_voice_style_guide_pipeline(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                artifacts_root=artifacts_root,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            # Ensure pipeline run is marked complete (idempotent)
            await _mark_pipeline_run_complete(session_factory, run_id)

            result = {
                "slug": output.slug,
                "company_name": output.company_name,
                "authors_discovered": output.authors_discovered,
                "authors_approved": output.authors_approved,
                "authors_researched": output.authors_researched,
                "guide_generated": output.guide_generated,
                "guide_dir": output.guide_dir,
                "style_guide_path": output.style_guide_path,
                "produced_artifacts": [
                    {"type": "voice_style_guide", "slug": scope.effective_slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result,
            )

    except asyncio.CancelledError:
        logger.info("VSG pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("VSG pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"voice_style_guide:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ---------------------------------------------------------------------------
# Research Orchestrator (KB → AP → VSG)
# ---------------------------------------------------------------------------


async def run_research_orchestrator_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> None:
    """Background task wrapper for Research Orchestrator (KB → AP → VSG).

    Acquires task_store semaphore ONCE for the entire orchestration.
    Sub-pipelines are called directly (not via runner wrappers).
    """
    from core.models.research_orchestrator import ResearchOrchestratorInput
    from core.research.orchestrator import run_research_orchestrator

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = None  # Ensure always defined for finally block
    session_factory: Any = None
    run_id: Any = None

    # All pre-run awaits inside try/finally for slug-lock safety (Codex Fix #8)
    bind_context(task_id=task_id, pipeline_name="research_orchestrator", company_slug=company_slug)
    try:
        scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

        session_factory, run_id, company_id = await _resolve_db_context(
            scope.company_slug, scope.effective_slug,
        )
        if session_factory and run_id and company_id:
            await _create_pipeline_run(
                session_factory, run_id, company_id,
                scope.effective_slug, "research_orchestrator",
            )
        if run_id:
            bind_context(run_id=str(run_id))

        async with task_store.semaphore:
            # Build auto-approve config
            auto_approve_raw = getattr(request, "auto_approve", None)
            auto_approve_dict = {}
            if auto_approve_raw:
                auto_approve_dict = {
                    "kb": getattr(auto_approve_raw, "kb", []),
                    "ap": getattr(auto_approve_raw, "ap", []),
                    "vsg": getattr(auto_approve_raw, "vsg", []),
                }

            # Wire skip_fresh flag into PipelineSkipConfig
            from core.models.research_orchestrator import PipelineSkipConfig
            skip_fresh = getattr(request, "skip_fresh", True)
            skip_config = PipelineSkipConfig(
                skip_kb_if_fresh=skip_fresh,
                skip_ap_if_fresh=skip_fresh,
                skip_vsg_if_fresh=skip_fresh,
            )

            input_data = ResearchOrchestratorInput(
                company_name=request.company_name,
                domain=getattr(request, "domain", ""),
                company_slug=scope.company_slug,
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                seed_urls=getattr(request, "seed_urls", []),
                staleness_threshold_days=getattr(request, "staleness_threshold_days", 30),
                max_personas=getattr(request, "max_personas", 5),
                max_authors=getattr(request, "max_authors", 3),
                language=getattr(request, "language", "en"),
                region=getattr(request, "region", None),
                additional_constraints=getattr(request, "additional_constraints", None),
                force_rerun=getattr(request, "force_rerun", False),
                auto_approve=auto_approve_dict,
                skip_config=skip_config,
                pipelines=getattr(request, "pipelines", ["kb", "ap", "vsg"]),
            )

            output = await run_research_orchestrator(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                artifacts_root=artifacts_root,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            result = {
                "slug": output.slug,
                "company_name": output.company_name,
                "effective_slug": output.effective_slug,
                "orchestrator_status": output.orchestrator_status.value,
                "pipelines_run": output.pipelines_run,
                "pipelines_skipped": output.pipelines_skipped,
                "total_execution_time_s": output.total_execution_time_s,
                "company_context_path": output.company_context_path,
                "persona_dir": output.persona_dir,
                "style_guide_path": output.style_guide_path,
                "produced_artifacts": [
                    {"type": p, "slug": scope.effective_slug}
                    for p in output.pipelines_run
                ],
            }

            # Map orchestrator failure to task-level FAILED status
            from core.models.research_orchestrator import OrchestratorStatus
            is_failed = output.orchestrator_status == OrchestratorStatus.failed
            task_status = TaskStatus.FAILED if is_failed else TaskStatus.COMPLETED

            # Extract error message from failed sub-pipeline for task.error
            error_msg = None
            if is_failed:
                for sr in output.sub_results.values():
                    if sr.error:
                        error_msg = sr.error
                        break

            task_store.update_task(
                task_id, status=task_status, result=result,
                **({"error": error_msg} if error_msg else {}),
            )

            # Mark DB pipeline run with correct terminal status
            if is_failed:
                await _mark_pipeline_run_failed(
                    session_factory, run_id, error_msg or "orchestrator failed",
                )
            else:
                await _mark_pipeline_run_complete(session_factory, run_id)

    except asyncio.CancelledError:
        logger.info("Research orchestrator cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Research orchestrator failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        _eff = scope.effective_slug if scope else company_slug
        task_store.release_slug_lock(f"research_orchestrator:{_eff}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ---------------------------------------------------------------------------
# Topic Discovery Pipeline
# ---------------------------------------------------------------------------


async def run_topic_discovery_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> None:
    """Background task wrapper for Topic Discovery pipeline."""
    from core.models.topic_discovery import TopicDiscoveryInput
    from core.topic_discovery.pipeline import run_topic_discovery_pipeline

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    # Resolve DB context for pipeline run tracking
    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "topic_discovery",
        )

    bind_context(task_id=task_id, pipeline_name="topic_discovery", company_slug=scope.company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            input_data = TopicDiscoveryInput(
                company_name=request.company_name,
                domain=getattr(request, "domain", None),
                company_slug=scope.company_slug,
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                auto_approve_checkpoints=getattr(request, "auto_approve_checkpoints", []),
                max_expansion_rounds=getattr(request, "max_expansion_rounds", 4),
                dedup_threshold=getattr(request, "dedup_threshold", 0.85),
                top_n_expand=getattr(request, "top_n_expand", 10),
                persona_filter=getattr(request, "persona_filter", None),
                language=getattr(request, "language", "en"),
                region=getattr(request, "region", None),
                additional_constraints=getattr(request, "additional_constraints", None),
            )

            output = await run_topic_discovery_pipeline(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                artifacts_root=artifacts_root,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            # Ensure pipeline run is marked complete (idempotent)
            await _mark_pipeline_run_complete(session_factory, run_id)

            result = {
                "slug": output.slug,
                "company_name": output.company_name,
                "taxonomy_version": output.taxonomy_version,
                "matrix_version": output.matrix_version,
                "total_subdomains": output.taxonomy.total_subdomains if output.taxonomy else 0,
                "total_assignments": output.matrix.total_assignments if output.matrix else 0,
                "coverage_score": output.taxonomy.coverage_score if output.taxonomy else 0.0,
                "produced_artifacts": [
                    {"type": "topic_discovery", "slug": scope.effective_slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result,
            )

    except asyncio.CancelledError:
        logger.info("TD pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("TD pipeline failed: %s", exc)
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(f"topic_discovery:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_topic_expansion_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> None:
    """Background task wrapper for Topic Expansion pipeline (Pipeline B)."""
    from core.models.topic_discovery import TopicExpansionInput
    from core.topic_discovery.pipeline import run_topic_expansion_pipeline

    company_slug = _derive_slug(request.company_name)
    product_slug = getattr(request, "product_slug", None)
    scope = await _resolve_scope_async(company_slug, product_slug, auth_service)

    session_factory, run_id, company_id = await _resolve_db_context(
        scope.company_slug, scope.effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            scope.effective_slug, "topic_expansion",
        )

    bind_context(task_id=task_id, pipeline_name="topic_expansion", company_slug=scope.company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            input_data = TopicExpansionInput(
                company_name=request.company_name,
                domain=getattr(request, "domain", None),
                company_slug=scope.company_slug,
                product_slug=scope.product_slug,
                product_name=scope.product_name,
                effective_slug=scope.effective_slug,
                subdomain_ids=getattr(request, "subdomain_ids", []),
                persona_filter=getattr(request, "persona_filter", None),
                taxonomy_version=getattr(request, "taxonomy_version", None),
                auto_approve_checkpoints=getattr(request, "auto_approve_checkpoints", []),
            )

            output = await run_topic_expansion_pipeline(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                artifacts_root=artifacts_root,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            await _mark_pipeline_run_complete(session_factory, run_id)

            result = {
                "slug": output.slug,
                "effective_slug": output.effective_slug,
                "matrix_version": output.matrix_version,
                "subdomains_expanded": output.subdomains_expanded,
                "subdomains_failed": output.subdomains_failed,
                "total_assignments": output.total_assignments,
                "produced_artifacts": [
                    {"type": "topic_expansion", "slug": scope.effective_slug},
                ],
            }
            task_store.update_task(
                task_id, status=TaskStatus.COMPLETED, result=result,
            )

    except asyncio.CancelledError:
        logger.info("TD-Expansion pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("TD-Expansion pipeline failed: %s", exc)
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        task_store.release_slug_lock(f"topic_expansion:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ── TD → Content pipeline runner ──────────────────────────────────


async def run_td_content_pipeline_task(
    task_id: str,
    effective_slug: str,
    topic_assignment_ids: List[str],
    company_name: str,
    domain: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    *,
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    auto_approve: bool = False,
    platforms: Optional[List[str]] = None,
) -> None:
    """Background task wrapper for the TD → GA → CE orchestrator.

    Acquires semaphore, resolves DB context, calls
    run_td_to_content_pipeline(), and handles completion/failure.
    """
    from core.orchestration.td_content_orchestrator import (
        run_td_to_content_pipeline,
    )

    company_slug = _derive_slug(company_name)

    session_factory, run_id, company_id = await _resolve_db_context(
        company_slug, effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            effective_slug, "content",
        )

    bind_context(task_id=task_id, pipeline_name="td_content", company_slug=company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "td_content"})

            output = await run_td_to_content_pipeline(
                effective_slug=effective_slug,
                topic_assignment_ids=topic_assignment_ids,
                company_name=company_name,
                domain=domain,
                platforms=platforms,
                auto_approve=auto_approve,
                product_slug=product_slug,
                product_name=product_name,
                product_description=product_description,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            result = {
                "company_slug": output.company_slug,
                "total_briefs": output.total_briefs,
                "total_approved": output.total_approved,
                "total_rejected": output.total_rejected,
                "pieces": [
                    {
                        "brief_id": p.brief_id,
                        "title": p.title,
                        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                        "topic_assignment_id": p.topic_assignment_id,
                    }
                    for p in output.pieces
                ],
                "produced_artifacts": [{"type": "td_content", "slug": effective_slug}],
            }
            task_store.update_task(task_id, status=TaskStatus.COMPLETED, result=result)
            event_bus.publish(task_id, "completed", {"pipeline": "td_content"})

    except asyncio.CancelledError:
        logger.info("TD→Content pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("TD→Content pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"td_content:{effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ---------------------------------------------------------------------------
# Onboarding Pipeline
# ---------------------------------------------------------------------------


async def run_onboarding_task(
    task_id: str,
    request: Any,
    company_name: str,
    company_domain: str,
    company_slug: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> None:
    """Background task wrapper for Onboarding Pipeline Orchestrator.

    Acquires task_store semaphore ONCE for the entire orchestration.
    company_name/domain/slug resolved by the router from auth context.
    """
    from core.models.onboarding import OnboardingInput, OnboardingStatus
    from core.onboarding.orchestrator import run_onboarding_pipeline

    session_factory: Any = None
    run_id: Any = None

    bind_context(task_id=task_id, pipeline_name="onboarding", company_slug=company_slug)
    try:
        session_factory, run_id, company_id = await _resolve_db_context(
            company_slug, company_slug,
        )
        if session_factory and run_id and company_id:
            await _create_pipeline_run(
                session_factory, run_id, company_id,
                company_slug, "onboarding",
            )
        if run_id:
            bind_context(run_id=str(run_id))

        async with task_store.semaphore:
            input_data = OnboardingInput(
                company_name=company_name,
                domain=company_domain,
                company_slug=company_slug,
                industry=getattr(request, "industry", None),
                seed_personas=getattr(request, "seed_personas", []),
                seed_urls=[str(u) for u in getattr(request, "seed_urls", [])],
                max_pages=getattr(request, "max_pages", 200),
                max_depth=getattr(request, "max_depth", 4),
                max_personas=getattr(request, "max_personas", 5),
                max_authors=getattr(request, "max_authors", 3),
                max_queries=getattr(request, "max_queries", 75),
                platforms=getattr(request, "platforms", ["perplexity", "openai", "gemini", "claude"]),
                language=getattr(request, "language", "en"),
                region=getattr(request, "region", None),
                force_rerun=getattr(request, "force_rerun", False),
            )

            output = await run_onboarding_pipeline(
                input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                artifacts_root=artifacts_root,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
            )

            result = {
                "slug": output.slug,
                "company_name": output.company_name,
                "onboarding_status": output.onboarding_status.value,
                "total_execution_time_s": output.total_execution_time_s,
                "audit_run_id": output.audit_run_id,
                "company_context_path": output.company_context_path,
                "persona_dir": output.persona_dir,
                "style_guide_path": output.style_guide_path,
                "gap_analysis_dir": output.gap_analysis_dir,
                "topic_discovery_id": output.topic_discovery_id,
                "phases": {
                    k: {"status": v.status, "time_s": v.execution_time_s}
                    for k, v in output.phases.items()
                },
                "produced_artifacts": [
                    {"type": sr.pipeline, "slug": company_slug}
                    for sr in output.sub_results.values()
                    if sr.status == "completed"
                ],
            }

            is_failed = output.onboarding_status == OnboardingStatus.failed
            task_status = TaskStatus.FAILED if is_failed else TaskStatus.COMPLETED

            error_msg = None
            if is_failed:
                for sr in output.sub_results.values():
                    if sr.error:
                        error_msg = sr.error
                        break

            task_store.update_task(
                task_id, status=task_status, result=result,
                **({"error": error_msg} if error_msg else {}),
            )

            if is_failed:
                await _mark_pipeline_run_failed(
                    session_factory, run_id, error_msg or "onboarding failed",
                )
            else:
                await _mark_pipeline_run_complete(session_factory, run_id)

    except asyncio.CancelledError:
        logger.info("Onboarding pipeline cancelled: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("Onboarding pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"onboarding:{company_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ── Daily Tracker pipeline runner ────────────────────────────────────


async def run_daily_tracker_task(
    task_id: str,
    request: Any,
    company_slug: str,
    artifacts_root: Path,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
) -> None:
    """Background task wrapper for the daily tracker pipeline.

    Builds the orchestrator internally, executes a daily run, and persists
    results to both filesystem (JSON artifact) and DB (daily_runs +
    daily_run_responses tables).

    Key design decisions (Codex-informed):
    - **company_slug is string**: daily_tracker tables use String company_id.
      ``_resolve_db_context``'s UUID company_id is only for PipelineRunModel.
    - **result.run_id → daily_runs.id**: The orchestrator generates run_id
      internally.  PipelineRunModel gets its own ``pipeline_run_id``.
    - **Two-phase daily_runs write**: ``create_daily_run_record`` (status=running)
      then ``persist_daily_run_result`` (status=completed/failed).
    - **Safety net**: ``mark_daily_run_failed`` in finally block ensures the
      daily_runs row never stays in 'running' state.

    Args:
        task_id: Task UUID created by the router.
        request: TriggerRunRequest fields (engines, prompt_ids, brand, etc.).
        company_slug: Authenticated company slug (string).
        artifacts_root: Filesystem root for artifact persistence.
        task_store: Task persistence store.
        event_bus: SSE event bus for real-time progress streaming.
    """
    session_factory: Any = None
    pipeline_run_id: Any = None
    daily_run_id: Optional[str] = None

    bind_context(task_id=task_id, pipeline_name="daily_tracker", company_slug=company_slug)
    try:
        # 1. Resolve DB context — session_factory for orchestrator + persistence,
        #    pipeline_run_id/company_id for PipelineRunModel only.
        session_factory, pipeline_run_id, company_id = await _resolve_db_context(
            company_slug, company_slug,
        )
        if session_factory and pipeline_run_id and company_id:
            await _create_pipeline_run(
                session_factory, pipeline_run_id, company_id,
                company_slug, "daily_tracker",
            )
        if pipeline_run_id:
            bind_context(run_id=str(pipeline_run_id))

        # 2. Daily tracker REQUIRES DB for prompt storage
        if session_factory is None:
            raise RuntimeError(
                "Daily tracker requires DATABASE_URL for prompt storage"
            )

        async with task_store.semaphore:
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "daily_tracker"})

            from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
            from core.daily_tracker.prompt_library import PromptLibraryService
            from core.daily_tracker.platform_runner import PlatformRunnerService
            from core.daily_tracker.mention_detector import MentionDetector
            from core.daily_tracker.orchestrator import DailyTrackerOrchestrator
            from core.daily_tracker.persistence import (
                create_daily_run_record,
                persist_daily_run_result,
                write_run_artifact,
            )
            from core.models.daily_tracker import RunStatus

            # 3. Pre-generate run_id and create daily_run record BEFORE
            #    orchestration for in-flight visibility in GET /runs.
            daily_run_id = str(uuid.uuid4())
            config = {
                "engines": getattr(request, "engines", None),
                "prompt_ids": getattr(request, "prompt_ids", None),
                "brand": getattr(request, "brand", None),
                "competitors": getattr(request, "competitors", None),
            }
            await create_daily_run_record(
                session_factory, company_slug, daily_run_id, config,
            )

            # 4. Build orchestrator with a short-lived DB session for prompt
            #    loading only. Session is released BEFORE external platform
            #    calls to avoid holding DB connections during long I/O.
            async with session_factory() as orch_session:
                prompt_repo = TrackedPromptRepository(orch_session)
                orchestrator = DailyTrackerOrchestrator(
                    prompt_service=PromptLibraryService(prompt_repo=prompt_repo),
                    runner_service=PlatformRunnerService(),
                    mention_detector=MentionDetector(),
                )

                # Pre-load prompts within the session scope
                prompts = await orchestrator._fetch_prompts(
                    company_slug,
                    getattr(request, "prompt_ids", None),
                )

            # 5. Execute orchestrator WITHOUT holding a DB connection.
            #    Pass pre-generated run_id so result.run_id matches the
            #    daily_runs row created above.
            result = await orchestrator.execute_daily_run(
                company_id=company_slug,
                prompt_ids=[p.id for p in prompts] if prompts else None,
                engines=getattr(request, "engines", None),
                brand=getattr(request, "brand", None),
                competitors=getattr(request, "competitors", None),
                concurrency=getattr(request, "concurrency", 6),
                run_id=daily_run_id,
            )

            mention_analyses: list[Any] = getattr(result, "_mention_analyses", [])

            # 6. Filesystem-first
            await write_run_artifact(
                artifacts_root, company_slug, result, mention_analyses,
            )

            # 7. DB-additive
            await persist_daily_run_result(
                session_factory, company_slug, result, mention_analyses,
            )

            # 8. Update task based on result status
            if result.status == RunStatus.FAILED:
                task_store.update_task(
                    task_id, status=TaskStatus.FAILED, error=result.error,
                )
                event_bus.publish(task_id, "failed", {"error": result.error or "Run failed"})
                await _mark_pipeline_run_failed(
                    session_factory, pipeline_run_id, result.error or "Run failed",
                )
            else:
                summary = {
                    "run_id": daily_run_id,
                    "prompt_count": result.prompt_count,
                    "engine_count": result.engine_count,
                }
                task_store.update_task(
                    task_id, status=TaskStatus.COMPLETED, result=summary,
                )
                event_bus.publish(task_id, "completed", {"pipeline": "daily_tracker"})
                await _mark_pipeline_run_complete(session_factory, pipeline_run_id, summary)

    except asyncio.CancelledError:
        logger.info("Daily tracker pipeline cancelled: task_id=%s", task_id)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error="Pipeline cancelled",
        )
        event_bus.publish(task_id, "failed", {"error": "Pipeline cancelled"})
        await _mark_pipeline_run_failed(session_factory, pipeline_run_id, "Cancelled")
    except Exception as exc:
        logger.exception("Daily tracker pipeline failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, pipeline_run_id, str(exc))
    finally:
        task_store.release_slug_lock(f"daily_tracker:{company_slug}")
        task_store.remove_task_handle(task_id)
        # Safety net: ensure daily_runs row doesn't stay in 'running' state
        if daily_run_id and session_factory:
            from core.daily_tracker.persistence import mark_daily_run_failed as _mark_dt_failed
            await _mark_dt_failed(session_factory, daily_run_id)
        clear_context()
