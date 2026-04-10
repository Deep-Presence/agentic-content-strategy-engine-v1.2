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

from api.config import api_settings
from api.tasks.event_bus import EventBusProtocol
from api.tasks.models import PipelineTask
from api.tasks.models import TaskStatus
from core.services.task_store import TaskStoreProtocol
from core.gap_analysis.pipeline import run_gap_analysis
from core.auth.utils.domain import derive_slug
from core.models.gap_analysis import GapAnalysisInput
from core.shared_tools.structured_logging import bind_context, clear_context
from core.cache import cache_delete, cache_delete_pattern
from core.redis import get_sync_redis_or_none

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/
_CONTENT_ENGINE_TASK_PIPELINES = {"content", "content_v13", "td_content"}
_TERMINAL_TASK_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.FAILED_RESTART,
}


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
    Always returns relative storage keys compatible with any backend.
    """
    from core.storage import get_storage_backend
    _backend = backend or get_storage_backend(artifacts_root)

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
            resolved["company_context_path"] = key
            break

    # Personas: via PersonaStorage
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
    artifacts_root: Optional[Path],
    effective_slug: str,
    *,
    redis_client: Optional[Any] = None,
    task_id: Optional[str] = None,
) -> None:
    """Best-effort removal of pipeline state on failure/cancel.

    **Redis (task-scoped):** Only removes briefs belonging to ``task_id``
    via ``__tid:`` field matching. This prevents clobbering other parallel
    manual runs sharing the same slug.

    **File:** Still does full file deletion (legacy behavior — parallel manual
    runs don't reliably write separate state files). File cleanup is kept as
    safety net for stale data prevention.
    """
    # Redis cleanup (task-scoped — only removes this run's briefs)
    if redis_client is not None:
        try:
            from core.content_engine.state_redis import cleanup_stale_pipeline_state_redis

            cleanup_stale_pipeline_state_redis(redis_client, effective_slug, task_id=task_id)
        except Exception:
            logger.warning("Redis stale state cleanup failed", exc_info=True)

    # File cleanup (always — dual cleanup for safety)
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
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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

            # Hydrate content inventory from S1 crawl (non-blocking)
            # Only when S1 actually ran — skipped S1 reuses stale artifacts
            if not (1 in (request.skip_steps or [])):
                try:
                    from core.content_inventory.hydration import (
                        hydrate_content_inventory_from_gap_analysis,
                    )

                    ga_prefix = f"gap_analysis/{scope.effective_slug}"
                    inventory_result = await hydrate_content_inventory_from_gap_analysis(
                        session_factory, company_id,
                        scope.effective_slug, run_id,
                        storage=_storage,
                        ga_prefix=ga_prefix,
                    )
                    if inventory_result:
                        logger.info(
                            "content_inventory.gap_analysis_hydrated",
                            extra={
                                "task_id": task_id,
                                "upserted": inventory_result.get("upserted", 0),
                            },
                        )
                except Exception:
                    logger.warning(
                        "content_inventory.gap_analysis_hydration_failed",
                        extra={"task_id": task_id},
                        exc_info=True,
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
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:gap:{scope.effective_slug}:*")
                cache_delete(_rc, f"cache:gap_ctx:{scope.effective_slug}")
        except Exception:
            pass
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
    event_bus: EventBusProtocol,
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

        async with task_store.pipeline_semaphore(task_id):
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

                html_map: dict[str, str] = {}
                audit_result = await run_site_audit(input_data, _html_map_out=html_map)

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

                # 3. Hydrate content inventory (non-blocking)
                from core.content_inventory.hydration import (
                    hydrate_content_inventory_from_site_audit,
                )

                inventory_result = await hydrate_content_inventory_from_site_audit(
                    session_factory, company_id,
                    scope.effective_slug, run_id, audit_result,
                    html_map=html_map,
                )
                del html_map  # Free ~20MB of raw HTML
                if inventory_result:
                    logger.info(
                        "content_inventory.hydrated",
                        extra={
                            "task_id": task_id,
                            "upserted": inventory_result.get("upserted", 0),
                            "skipped": inventory_result.get("skipped", 0),
                        },
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
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:audit:{scope.effective_slug}:*")
        except Exception:
            pass
        task_store.release_slug_lock(f"site_audit:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_content_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(
            task_id,
            pool="content_engine",
            company_slug=company_slug,
        ):
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
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:content:{effective}:*")
        except Exception:
            pass
        task_store.release_slug_lock(f"content:{effective}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_content_v13_pipeline_task(
    task_id: str,
    input_data: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    artifacts_root: Optional[Path] = None,
    *,
    is_parallel: bool = False,
) -> None:
    """Background task wrapper for v1.3 content generation pipeline.

    Follows the same semaphore + slug-lock + handle pattern as
    run_content_pipeline_task. Uses the company-scoped content-engine
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

    # Obtain async Redis client for pipeline state writes (non-blocking)
    # + sync Redis client for error-path cleanup (sync file ops anyway)
    _redis_async = None
    _redis_sync = None
    try:
        from core.config.settings import settings as _cfg
        if _cfg.redis_pipeline_state and _cfg.redis_url:
            from core.redis import get_redis_or_none
            _redis_async = get_redis_or_none()
            _redis_sync = get_sync_redis_or_none()  # module-level import
    except Exception:
        pass

    try:
        async with task_store.pipeline_semaphore(
            task_id,
            pool="content_engine",
            company_slug=company_slug,
        ):
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "content_v13"})

            output = await run_content_generation_v13(
                input_data=input_data,
                task_id=task_id,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
                run_id=run_id,
                company_id=company_id,
                redis_client=_redis_async,
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
        _cleanup_stale_pipeline_state(artifacts_root, effective, redis_client=_redis_sync, task_id=task_id)
    except Exception as exc:
        logger.exception("Content v1.3 pipeline failed: %s", exc)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
        _cleanup_stale_pipeline_state(artifacts_root, effective, redis_client=_redis_sync, task_id=task_id)
    finally:
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:content:{effective}:*")
        except Exception:
            pass
        if not is_parallel:
            task_store.release_slug_lock(f"content_v13:{effective}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ── Knowledge Base pipeline runner ─────────────────────────────────


async def run_kb_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:brand:{scope.effective_slug}:*")
        except Exception:
            pass
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
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:brand:{scope.effective_slug}:*")
        except Exception:
            pass
        task_store.release_slug_lock(f"audience_persona:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_single_persona_generator_task(
    task_id: str,
    persona_id: str,
    slug: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    artifacts_root: Any = None,
) -> None:
    """Background task for standalone single-persona generation."""
    from core.models.audience_persona import AudiencePersonaInput
    from core.research.audience_persona.agents import run_persona_profile_generator
    from core.research.audience_persona.pipeline import _preflight_check
    from core.research.audience_persona.storage import PersonaStorage

    bind_context(task_id=task_id, pipeline_name="audience_persona", company_slug=slug)
    try:
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
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
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:brand:{scope.effective_slug}:*")
        except Exception:
            pass
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
    event_bus: EventBusProtocol,
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

        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        _eff = scope.effective_slug if scope else company_slug
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:brand:{_eff}:*")
        except Exception:
            pass
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
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        task_store.release_slug_lock(f"topic_discovery:{scope.effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def run_topic_expansion_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        # No slug lock to release — topic expansion uses allow_parallel=True.
        # Per-subdomain concurrency is handled by db_claim_subdomain_for_expansion().
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
    event_bus: EventBusProtocol,
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
        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
        task_store.release_slug_lock(f"td_content:{effective_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


# ── TD → GA-only pipeline runner ─────────────────────────────────────


async def run_td_gap_analysis_task(
    task_id: str,
    effective_slug: str,
    topic_assignment_ids: List[str],
    company_name: str,
    domain: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    *,
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    platforms: Optional[List[str]] = None,
) -> None:
    """Background task wrapper for the TD → GA-only orchestrator (Phase 1).

    Acquires semaphore, resolves DB context, calls
    run_td_gap_analysis_only(), and handles completion/failure.
    """
    from core.orchestration.td_content_orchestrator import (
        run_td_gap_analysis_only,
        _update_assignment_statuses_db,
        _cleanup_ga_phase_redis,
    )
    from core.models.topic_discovery import TopicAssignmentStatus
    from core.services.content_engine_topic_runs import ContentEngineTopicRunService

    company_slug = _derive_slug(company_name)

    session_factory, run_id, company_id = await _resolve_db_context(
        company_slug, effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            effective_slug, "td_gap_analysis",
        )
    topic_run_service = (
        ContentEngineTopicRunService(session_factory)
        if session_factory is not None
        else None
    )

    bind_context(task_id=task_id, pipeline_name="td_gap_analysis", company_slug=company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.pipeline_semaphore(task_id):
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "td_gap_analysis"})

            ga_result = await run_td_gap_analysis_only(
                effective_slug=effective_slug,
                topic_assignment_ids=topic_assignment_ids,
                company_name=company_name,
                domain=domain,
                platforms=platforms,
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
                "ga_run_id": ga_result.ga_run_id,
                "analysis_path": ga_result.analysis_path,
                "topic_assignment_ids": ga_result.valid_assignment_ids,
                "produced_artifacts": [{"type": "td_gap_analysis", "slug": effective_slug}],
            }
            task_store.update_task(task_id, status=TaskStatus.COMPLETED, result=result)
            event_bus.publish(task_id, "completed", {"pipeline": "td_gap_analysis", "ga_run_id": ga_result.ga_run_id})
            if topic_run_service is not None and ga_result.valid_assignment_ids:
                try:
                    await topic_run_service.advance_topic_runs(
                        effective_slug=effective_slug,
                        topic_assignment_ids=ga_result.valid_assignment_ids,
                        status="gap_analysis_complete",
                        stage="gap_analysis_complete",
                        pipeline_task_id=task_id,
                        ga_run_id=ga_result.ga_run_id,
                        match_pipeline_task_id=task_id,
                        payload_json={
                            "source": "td_gap_analysis",
                            "note": "Gap analysis completed",
                            "ga_run_id": ga_result.ga_run_id,
                        },
                    )
                except Exception:
                    logger.warning("Failed to persist durable GA completion state", exc_info=True)

    except asyncio.CancelledError:
        logger.info("TD→GA pipeline cancelled: task_id=%s", task_id)
        # Revert assignment statuses and clean up GA-phase Redis state
        if session_factory:
            try:
                await _update_assignment_statuses_db(
                    session_factory, topic_assignment_ids,
                    TopicAssignmentStatus.approved,
                )
            except Exception:
                logger.warning("Failed to revert assignment statuses on GA cancel", exc_info=True)
            try:
                _cleanup_ga_phase_redis(effective_slug, topic_assignment_ids)
            except Exception:
                logger.warning("Failed to clean up GA-phase Redis state on cancel", exc_info=True)
        if topic_run_service is not None:
            try:
                await topic_run_service.advance_topic_runs(
                    effective_slug=effective_slug,
                    topic_assignment_ids=topic_assignment_ids,
                    status="cancelled",
                    stage="cancelled",
                    pipeline_task_id=task_id,
                    match_pipeline_task_id=task_id,
                    last_error="Cancelled",
                    payload_json={
                        "source": "td_gap_analysis",
                        "note": "Gap analysis was cancelled",
                    },
                )
            except Exception:
                logger.warning("Failed to persist durable GA cancel state", exc_info=True)
        task_store.update_task(task_id, status=TaskStatus.CANCELLED, error="Cancelled")
        event_bus.publish(task_id, "cancelled", {"pipeline": "td_gap_analysis"})
    except Exception as exc:
        logger.exception("TD→GA pipeline failed: %s", exc)
        # Revert assignment statuses back to approved
        if session_factory:
            try:
                await _update_assignment_statuses_db(
                    session_factory, topic_assignment_ids,
                    TopicAssignmentStatus.approved,
                )
            except Exception:
                logger.warning("Failed to revert assignment statuses on GA failure", exc_info=True)
            # Clean up GA-phase Redis state
            try:
                _cleanup_ga_phase_redis(effective_slug, topic_assignment_ids)
            except Exception:
                logger.warning("Failed to clean up GA-phase Redis state", exc_info=True)
        if topic_run_service is not None:
            try:
                await topic_run_service.advance_topic_runs(
                    effective_slug=effective_slug,
                    topic_assignment_ids=topic_assignment_ids,
                    status="failed",
                    stage="failed",
                    pipeline_task_id=task_id,
                    match_pipeline_task_id=task_id,
                    last_error=str(exc),
                    payload_json={
                        "source": "td_gap_analysis",
                        "note": "Gap analysis failed",
                        "error": str(exc),
                    },
                )
            except Exception:
                logger.warning("Failed to persist durable GA failure state", exc_info=True)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        await task_store.flush_terminal(task_id)
        # No slug lock to release — td_gap_analysis now uses allow_parallel=True.
        # Releasing here would risk popping a different run's lock.
        task_store.remove_task_handle(task_id)
        clear_context()


# ── TD → Content production-only pipeline runner ─────────────────────


def _count_active_company_ce_tasks(
    task_store: TaskStoreProtocol,
    *,
    company_slug: str,
) -> int:
    tasks = task_store.list_tasks(company_slug=company_slug)
    return sum(
        1
        for task in tasks
        if task.pipeline in _CONTENT_ENGINE_TASK_PIPELINES
        and task.status != TaskStatus.PENDING_APPROVAL
        and task.status not in _TERMINAL_TASK_STATUSES
    )


async def _create_td_content_dispatch_task(
    *,
    task_store: TaskStoreProtocol,
    company_slug: str,
    product_slug: str | None,
) -> PipelineTask | None:
    task = task_store.create_task(
        "td_content",
        company_slug,
        product_slug,
        allow_parallel=True,
    )
    try:
        await task_store.ensure_created(task.task_id)
    except Exception:
        logger.exception(
            "Failed to persist dispatched td_content task for %s",
            company_slug,
        )
        if hasattr(task_store, "rollback_create"):
            task_store.rollback_create(task.task_id)
        return None
    return task


def _reuse_td_content_dispatch_task(
    *,
    task_store: TaskStoreProtocol,
    task_id: str,
) -> PipelineTask | None:
    try:
        return task_store.get_task(task_id)
    except Exception:
        logger.warning("Queued TD continuation task missing from task store", extra={"task_id": task_id})
        return None


async def dispatch_queued_td_content_runs(
    *,
    company_slug: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> list[dict[str, str]]:
    """Claim queued TD production topic runs and launch up to company capacity."""
    if session_factory is None:
        return []

    available_slots = max(
        api_settings.max_concurrent_content_engine_per_company
        - _count_active_company_ce_tasks(task_store, company_slug=company_slug),
        0,
    )
    if available_slots <= 0:
        return []

    from core.services.content_engine_topic_runs import ContentEngineTopicRunService

    service = ContentEngineTopicRunService(session_factory)
    claims = await service.claim_queued_topic_runs(
        company_slug=company_slug,
        limit=available_slots,
    )
    if not claims:
        return []

    dispatched_topic_runs: dict[str, str] = {}
    launch_payloads: list[tuple[Any, PipelineTask, dict[str, Any] | None]] = []
    undispatched_claim_ids: list[str] = []

    for claim in claims:
        launch_context = claim.launch_context or {}
        company_name = launch_context.get("company_name")
        domain = launch_context.get("domain")
        if not company_name or not domain or not claim.ga_run_id:
            undispatched_claim_ids.append(claim.topic_run_id)
            logger.warning(
                "Skipping queued TD topic run without launch context",
                extra={
                    "company_slug": company_slug,
                    "topic_run_id": claim.topic_run_id,
                    "display_id": claim.display_id,
                },
            )
            continue

        is_resume = bool(claim.continuation_payload)
        resume_payload = claim.continuation_payload if is_resume else None
        if is_resume and claim.pipeline_task_id:
            task = _reuse_td_content_dispatch_task(
                task_store=task_store,
                task_id=claim.pipeline_task_id,
            )
        else:
            task = await _create_td_content_dispatch_task(
                task_store=task_store,
                company_slug=company_slug,
                product_slug=launch_context.get("product_slug"),
            )
        if task is None:
            undispatched_claim_ids.append(claim.topic_run_id)
            continue

        dispatched_topic_runs[claim.topic_run_id] = task.task_id
        launch_payloads.append((claim, task, resume_payload))

    if undispatched_claim_ids:
        await service.release_topic_run_claims(topic_run_ids=undispatched_claim_ids)

    if not dispatched_topic_runs:
        return []

    try:
        await service.mark_claimed_topic_runs_dispatched(
            topic_run_task_ids=dispatched_topic_runs,
        )
    except Exception:
        logger.exception(
            "Failed to mark claimed TD topic runs as dispatched",
            extra={"company_slug": company_slug},
        )
        await service.release_topic_run_claims(
            topic_run_ids=list(dispatched_topic_runs.keys())
        )
        for _claim, task, _resume_payload in launch_payloads:
            task_store.update_task(
                task.task_id,
                status=TaskStatus.FAILED,
                error="Dispatcher failed before task launch",
            )
            await task_store.flush_terminal(task.task_id)
        return []

    results: list[dict[str, str]] = []
    for claim, task, resume_payload in launch_payloads:
        launch_context = claim.launch_context or {}
        if resume_payload is not None:
            task_store.update_task(
                task.task_id,
                status=TaskStatus.RUNNING,
                error=None,
                approval_payload=None,
            )
        handle = asyncio.create_task(
            run_td_content_production_task(
                task_id=task.task_id,
                effective_slug=claim.effective_slug,
                topic_assignment_ids=[claim.topic_assignment_id],
                company_name=launch_context["company_name"],
                domain=launch_context["domain"],
                ga_run_id=claim.ga_run_id or "",
                task_store=task_store,
                event_bus=event_bus,
                product_slug=launch_context.get("product_slug"),
                product_name=launch_context.get("product_name"),
                product_description=launch_context.get("product_description"),
                auto_approve=bool(launch_context.get("auto_approve", False)),
                td_resume_payload=resume_payload,
                td_resume_approval=(
                    dict(resume_payload.get("approval_data", {}))
                    if resume_payload
                    else None
                ),
            )
        )
        task_store.register_task_handle(task.task_id, handle)
        results.append(
            {
                "topic_run_id": claim.topic_run_id,
                "topic_assignment_id": claim.topic_assignment_id,
                "task_id": task.task_id,
            }
        )
    return results


async def run_td_content_production_task(
    task_id: str,
    effective_slug: str,
    topic_assignment_ids: List[str],
    company_name: str,
    domain: str,
    ga_run_id: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    *,
    product_slug: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    auto_approve: bool = False,
    td_resume_payload: Optional[Dict[str, Any]] = None,
    td_resume_approval: Optional[Dict[str, Any]] = None,
) -> None:
    """Background task wrapper for the TD → Content production-only orchestrator (Phase 2).

    Acquires semaphore, resolves DB context, calls
    run_td_content_production_only(), and handles completion/failure.
    """
    from core.orchestration.td_content_orchestrator import (
        run_td_content_production_only,
        _update_assignment_statuses_db,
        _update_ga_phase_status,
        _emit_company_event,
    )
    from core.content_engine.graph_v13 import ApprovalPauseRequested
    from core.models.topic_discovery import TopicAssignmentStatus
    from core.services.content_engine_topic_runs import ContentEngineTopicRunService

    company_slug = _derive_slug(company_name)

    session_factory, run_id, company_id = await _resolve_db_context(
        company_slug, effective_slug,
    )
    if session_factory and run_id and company_id:
        await _create_pipeline_run(
            session_factory, run_id, company_id,
            effective_slug, "content",
        )
    topic_run_service = (
        ContentEngineTopicRunService(session_factory)
        if session_factory is not None
        else None
    )

    bind_context(task_id=task_id, pipeline_name="td_content_production", company_slug=company_slug, run_id=str(run_id) if run_id else None)
    try:
        async with task_store.pipeline_semaphore(
            task_id,
            pool="content_engine",
            company_slug=company_slug,
        ):
            if topic_run_service is not None and td_resume_payload is None:
                try:
                    await topic_run_service.advance_topic_runs(
                        effective_slug=effective_slug,
                        topic_assignment_ids=topic_assignment_ids,
                        status="briefing",
                        stage="briefing",
                        ga_run_id=ga_run_id,
                        match_ga_run_id=ga_run_id,
                        pipeline_task_id=task_id,
                        payload_json={
                            "source": "td_content_production",
                            "note": "Content production started",
                            "ga_run_id": ga_run_id,
                        },
                    )
                except Exception:
                    logger.warning("Failed to persist durable production start state", exc_info=True)
            event_bus.publish(task_id, "pipeline_start", {"pipeline": "td_content"})

            output = await run_td_content_production_only(
                effective_slug=effective_slug,
                topic_assignment_ids=topic_assignment_ids,
                company_name=company_name,
                domain=domain,
                ga_run_id=ga_run_id,
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
                td_resume_payload=td_resume_payload,
                td_resume_approval=td_resume_approval,
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
            if topic_run_service is not None:
                try:
                    await _advance_td_topic_runs_for_output(
                        topic_run_service=topic_run_service,
                        effective_slug=effective_slug,
                        topic_assignment_ids=topic_assignment_ids,
                        output=output,
                        pipeline_task_id=task_id,
                        ga_run_id=ga_run_id,
                    )
                except Exception:
                    logger.warning("Failed to persist durable production completion state", exc_info=True)

    except ApprovalPauseRequested as exc:
        logger.info(
            "TD→Content production paused for approval",
            extra={"task_id": task_id, "company_slug": company_slug},
        )
        continuation_payload = dict(exc.approval_payload.get("continuation") or {})
        if topic_run_service is not None and continuation_payload:
            try:
                await topic_run_service.mark_topic_run_waiting_human(
                    effective_slug=effective_slug,
                    pipeline_task_id=task_id,
                    status=str(exc.approval_payload.get("status") or "pending_approval"),
                    stage=str(exc.approval_payload.get("stage") or "pending_approval"),
                    continuation_payload=continuation_payload,
                    payload_json={
                        "source": "td_content_production",
                        "note": "Waiting for human approval before continuing",
                        "approval_stage": exc.approval_payload.get("stage"),
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to persist durable approval wait state",
                    exc_info=True,
                )
    except asyncio.CancelledError:
        logger.info("TD→Content production pipeline cancelled: task_id=%s", task_id)
        _cleanup_stale_pipeline_state(_PROJECT_ROOT / "artifacts", effective_slug, redis_client=get_sync_redis_or_none(), task_id=task_id)
    except Exception as exc:
        logger.exception("TD→Content production pipeline failed: %s", exc)
        # Clean up stale CE pipeline state (brief-level entries like 'revising', 'evaluating')
        # Without this, stale entries block future pipeline launches with 409 and
        # cause ghost cards in the Kanban.
        _cleanup_stale_pipeline_state(_PROJECT_ROOT / "artifacts", effective_slug, redis_client=get_sync_redis_or_none(), task_id=task_id)
        # Revert assignment statuses back to gap_analysis_complete (DB + Redis + SSE)
        # F18 fix: Redis GA-phase state must also be reverted, not just DB.
        # Without this, cards stay stuck in 'briefing' in the Kanban.
        try:
            _update_ga_phase_status(
                effective_slug, topic_assignment_ids,
                "gap_analysis_complete", task_id=task_id,
            )
        except Exception:
            logger.warning("Failed to revert Redis GA-phase on production failure", exc_info=True)
        if session_factory:
            try:
                await _update_assignment_statuses_db(
                    session_factory, topic_assignment_ids,
                    TopicAssignmentStatus.gap_analysis_complete,
                )
            except Exception:
                logger.warning("Failed to revert assignment statuses on production failure", exc_info=True)
        try:
            _emit_company_event(effective_slug, "state_changed", {
                "changed": topic_assignment_ids, "hint": "gap_analysis_complete",
            })
        except Exception:
            pass  # Best-effort SSE
        if topic_run_service is not None:
            try:
                await topic_run_service.advance_topic_runs(
                    effective_slug=effective_slug,
                    topic_assignment_ids=topic_assignment_ids,
                    status="gap_analysis_complete",
                    stage="gap_analysis_complete",
                    pipeline_task_id=task_id,
                    ga_run_id=ga_run_id,
                    match_ga_run_id=ga_run_id,
                    last_error=str(exc),
                    payload_json={
                        "source": "td_content_production",
                        "note": "Content production failed; card returned to gap analysis complete",
                        "rollback_target": "gap_analysis_complete",
                        "ga_run_id": ga_run_id,
                        "error": str(exc),
                    },
                )
            except Exception:
                logger.warning("Failed to persist durable production failure state", exc_info=True)
        task_store.update_task(task_id, status=TaskStatus.FAILED, error=str(exc))
        event_bus.publish(task_id, "failed", {"error": str(exc)})
        await _mark_pipeline_run_failed(session_factory, run_id, str(exc))
    finally:
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:content:{effective_slug}:*")
        except Exception:
            pass
        try:
            await dispatch_queued_td_content_runs(
                company_slug=company_slug,
                task_store=task_store,
                event_bus=event_bus,
                session_factory=session_factory,
            )
        except Exception:
            logger.warning(
                "Failed to dispatch queued TD content runs after task completion",
                extra={"company_slug": company_slug, "task_id": task_id},
                exc_info=True,
            )
        # No slug lock to release — start-production uses allow_parallel=True.
        # Calling release_slug_lock here would pop a *different* locked run's
        # entry from _slug_locks, causing cross-talk (Codex finding).
        task_store.remove_task_handle(task_id)
        clear_context()


def _td_terminal_state_for_piece(piece: Any) -> tuple[str, str, str | None, dict[str, Any]]:
    """Derive the durable terminal topic-run state for one TD content piece."""
    status = getattr(piece, "status", None)
    status_value = status.value if hasattr(status, "value") else str(status or "")
    eval_summary = getattr(piece, "eval_summary", {}) or {}

    if eval_summary.get("worker_error"):
        return (
            "failed",
            "failed",
            str(eval_summary.get("worker_error")),
            {
                "source": "td_content_output",
                "note": "Worker failed during content production",
                "content_piece_status": status_value or "rejected",
                "worker_error": str(eval_summary.get("worker_error")),
            },
        )

    if status_value in {"approved", "edited"}:
        return (
            "content_produced",
            "completed",
            None,
            {
                "source": "td_content_output",
                "note": "Content production completed",
                "content_piece_status": status_value,
            },
        )
    if status_value == "rejected":
        return (
            "rejected",
            "rejected",
            None,
            {
                "source": "td_content_output",
                "note": "Content was rejected",
                "content_piece_status": status_value,
            },
        )
    return (
        "failed",
        "failed",
        f"Unexpected terminal piece status: {status_value or 'unknown'}",
        {
            "source": "td_content_output",
            "note": "Content production ended in an unexpected terminal state",
            "content_piece_status": status_value or "unknown",
        },
    )


async def _advance_td_topic_runs_for_output(
    *,
    topic_run_service: Any,
    effective_slug: str,
    topic_assignment_ids: list[str],
    output: Any,
    pipeline_task_id: str,
    ga_run_id: str,
) -> None:
    """Persist per-topic terminal CE outcomes without clobbering mixed batches."""
    grouped: dict[tuple[str, str, str | None, str, str], list[str]] = {}
    payload_by_group: dict[tuple[str, str, str | None, str, str], dict[str, Any]] = {}
    content_piece_ids_by_group: dict[tuple[str, str, str | None, str, str], dict[str, str]] = {}
    covered_assignment_ids: set[str] = set()

    for piece in getattr(output, "pieces", []) or []:
        topic_assignment_id = getattr(piece, "topic_assignment_id", None)
        if not topic_assignment_id:
            continue

        assignment_id = str(topic_assignment_id)
        covered_assignment_ids.add(assignment_id)
        status, stage, last_error, payload_json = _td_terminal_state_for_piece(piece)
        group_key = (
            status,
            stage,
            last_error,
            str(payload_json.get("note") or ""),
            str(payload_json.get("content_piece_status") or ""),
        )
        grouped.setdefault(group_key, []).append(assignment_id)
        payload_by_group[group_key] = payload_json

        piece_id = getattr(piece, "id", None)
        if piece_id:
            content_piece_ids_by_group.setdefault(group_key, {})[assignment_id] = str(piece_id)

    unresolved_assignment_ids = [
        str(topic_assignment_id)
        for topic_assignment_id in topic_assignment_ids
        if str(topic_assignment_id) not in covered_assignment_ids
    ]
    if unresolved_assignment_ids:
        unresolved_payload = {
            "source": "td_content_output",
            "note": "No terminal content outcome was recorded for this card",
        }
        unresolved_key = (
            "failed",
            "failed",
            "No terminal content outcome recorded for topic assignment",
            str(unresolved_payload["note"]),
            "",
        )
        grouped.setdefault(unresolved_key, []).extend(unresolved_assignment_ids)
        payload_by_group[unresolved_key] = unresolved_payload

    if not grouped:
        fallback_payload = {
            "source": "td_content_output",
            "note": "No content pieces were produced; card remains retryable",
            "rollback_target": "gap_analysis_complete",
        }
        fallback_key = (
            "gap_analysis_complete",
            "gap_analysis_complete",
            None,
            str(fallback_payload["note"]),
            "",
        )
        grouped[fallback_key] = [
            str(topic_assignment_id) for topic_assignment_id in topic_assignment_ids
        ]
        payload_by_group[fallback_key] = fallback_payload

    for group_key, assignment_ids in grouped.items():
        status, stage, last_error, _, _ = group_key
        await topic_run_service.advance_topic_runs(
            effective_slug=effective_slug,
            topic_assignment_ids=assignment_ids,
            status=status,
            stage=stage,
            pipeline_task_id=pipeline_task_id,
            ga_run_id=ga_run_id,
            match_ga_run_id=ga_run_id,
            content_piece_ids=content_piece_ids_by_group.get(group_key, {}),
            last_error=last_error,
            payload_json=payload_by_group.get(group_key),
        )


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
    event_bus: EventBusProtocol,
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

        async with task_store.pipeline_semaphore(task_id):
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
        await task_store.flush_terminal(task_id)
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
    event_bus: EventBusProtocol,
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

        async with task_store.pipeline_semaphore(task_id):
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

            # 3. Resolve competitors: explicit request > KB auto-resolve > none.
            #    Done BEFORE config persistence so audit trail includes actual list used.
            resolved_competitors = getattr(request, "competitors", None)
            if not resolved_competitors:
                try:
                    from core.research.knowledge_base.extraction import resolve_competitors_from_kb
                    from core.storage import get_storage_backend

                    kb_competitors = await asyncio.to_thread(
                        resolve_competitors_from_kb, company_slug, get_storage_backend(),
                    )
                    if kb_competitors:
                        resolved_competitors = kb_competitors
                        logger.info(
                            "Auto-resolved %d competitors from KB for %s: %s",
                            len(kb_competitors), company_slug,
                            ", ".join(kb_competitors[:5]),
                        )
                except Exception:
                    logger.warning("KB competitor auto-resolution failed", exc_info=True)

            # 4. Pre-generate run_id and create daily_run record BEFORE
            #    orchestration for in-flight visibility in GET /runs.
            daily_run_id = str(uuid.uuid4())
            config = {
                "engines": getattr(request, "engines", None),
                "prompt_ids": getattr(request, "prompt_ids", None),
                "brand": getattr(request, "brand", None),
                "competitors": resolved_competitors,
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

                # Pre-load prompts (parents + fanouts) within session scope
                all_prompts, fanout_map = await orchestrator._fetch_prompts_with_fanouts(
                    company_slug,
                    getattr(request, "prompt_ids", None),
                )

            result = await orchestrator.execute_daily_run(
                company_id=company_slug,
                prompt_ids=[p.id for p in all_prompts] if all_prompts else None,
                engines=getattr(request, "engines", None),
                brand=getattr(request, "brand", None),
                competitors=resolved_competitors,
                concurrency=getattr(request, "concurrency", 6),
                run_id=daily_run_id,
            )

            # Attach fanout parent map for persistence layer
            result._fanout_parent_map = fanout_map  # type: ignore[attr-defined]

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
        await task_store.flush_terminal(task_id)
        task_store.release_slug_lock(f"daily_tracker:{company_slug}")
        task_store.remove_task_handle(task_id)
        # Safety net: ensure daily_runs row doesn't stay in 'running' state
        if daily_run_id and session_factory:
            from core.daily_tracker.persistence import mark_daily_run_failed as _mark_dt_failed
            await _mark_dt_failed(session_factory, daily_run_id)
        # Invalidate enriched prompt cache after run completes
        try:
            from core.cache import cache_delete_pattern
            await asyncio.to_thread(
                cache_delete_pattern, f"cache:prompt_enriched:{company_slug}:*"
            )
        except Exception:
            logger.debug("Cache invalidation skipped (Redis unavailable)")
        clear_context()


# ── Query fanout generation runner ──────────────────────────────────


async def run_fanout_generation_task(
    task_id: str,
    parent_prompt_id: str,
    company_slug: str,
    brand_name: str,
    brand_category: str,
    competitors: list[str],
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
) -> None:
    """Background task: generate fanout queries for a parent prompt.

    Calls ``QueryFanoutService.generate_fanout()`` to produce query
    variants via OpenRouter, then persists them as child rows in
    ``tracked_prompts`` via ``PromptLibraryService.create_fanout_queries()``.

    Args:
        task_id: Task UUID created by the router.
        parent_prompt_id: UUID string of the parent prompt.
        company_slug: Company slug string.
        brand_name: Brand name for fanout context.
        brand_category: Brand category string.
        competitors: List of competitor names.
        task_store: Task persistence store.
        event_bus: SSE event bus for real-time progress streaming.
    """
    session_factory: Any = None
    bind_context(task_id=task_id, pipeline_name="fanout_generation", company_slug=company_slug)
    try:
        session_factory, _, _ = await _resolve_db_context(
            company_slug, company_slug,
        )
        if session_factory is None:
            raise RuntimeError("Fanout generation requires DATABASE_URL")

        event_bus.publish(task_id, "fanout_start", {
            "parent_prompt_id": parent_prompt_id,
        })

        from core.config.settings import settings
        from core.daily_tracker.query_fanout import QueryFanoutService
        from core.daily_tracker.prompt_library import PromptLibraryService
        from core.db.repositories.daily_tracker_repo import TrackedPromptRepository

        # Fetch parent prompt text first
        async with session_factory() as session:
            repo = TrackedPromptRepository(session)
            parent_orm = await repo.get_by_id(parent_prompt_id)
            if parent_orm is None:
                raise ValueError(f"Parent prompt {parent_prompt_id} not found")
            parent_text = parent_orm.text

        # Generate fanout queries via LLM (single call)
        fanout_service = QueryFanoutService(
            model=settings.daily_tracker_fanout_model,
            temperature=settings.daily_tracker_fanout_temperature,
        )
        gen_result = await fanout_service.generate_fanout(
            parent_text=parent_text,
            brand_name=brand_name,
            brand_category=brand_category,
            competitors=competitors,
            target_count=settings.daily_tracker_fanout_target_count,
        )

        # Persist fanout queries as tracked_prompts children
        async with session_factory() as session:
            repo = TrackedPromptRepository(session)
            prompt_service = PromptLibraryService(prompt_repo=repo)
            created = await prompt_service.create_fanout_queries(
                parent_prompt_id=parent_prompt_id,
                company_id=company_slug,
                queries=gen_result.queries,
            )
            await session.commit()

        task_store.update_task(
            task_id, status=TaskStatus.COMPLETED,
            result={
                "parent_prompt_id": parent_prompt_id,
                "fanout_count": len(created),
                "model_used": gen_result.model_used,
            },
        )
        event_bus.publish(task_id, "fanout_complete", {
            "parent_prompt_id": parent_prompt_id,
            "fanout_count": len(created),
        })

    except Exception as exc:
        logger.exception("Fanout generation failed: %s", exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        await task_store.flush_terminal(task_id)
        task_store.remove_task_handle(task_id)
        clear_context()


# ── CMS sync pipeline runner ────────────────────────────────────────


async def run_cms_sync_task(
    task_id: str,
    company_slug: str,
    tenant_id: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    session_factory: Any,
    storage: Any,
    fernet_key: str,
) -> None:
    """Background task wrapper for CMS content sync.

    Creates its own DB session and CMSService instance (the DI session
    from the router is closed by the time the background task runs).

    After sync completes, automatically generates AI visibility prompts
    for any **newly discovered** pages (capped at ``auto_prompt_max_pages``).
    Prompt generation failures do NOT fail the overall sync task.
    """
    bind_context(task_id=task_id, pipeline_name="cms_sync", company_slug=company_slug)
    task_store.update_task(task_id, status=TaskStatus.RUNNING, current_step="sync")
    event_bus.publish(task_id, "pipeline_start", {"pipeline": "cms_sync"})

    try:
        async with task_store.pipeline_semaphore(task_id):
            from core.db.repositories.cms_repo import (
                CMSConnectionRepository,
                CMSPublishRecordRepository,
                CMSSyncedPostRepository,
            )
            from core.services.cms_service import CMSService

            # Build inventory service for content inventory hydration
            inventory_svc = None
            try:
                from core.db.repositories.content_inventory_repo import (
                    ContentInventoryRepository,
                )
                from core.services.content_inventory_service import (
                    ContentInventoryService,
                )
            except ImportError:
                ContentInventoryRepository = None  # type: ignore[assignment,misc]
                ContentInventoryService = None  # type: ignore[assignment,misc]

            # ── Phase 1: CMS Sync ─────────────────────────────────────
            session = session_factory()
            try:
                if ContentInventoryRepository is not None:
                    inventory_svc = ContentInventoryService(
                        inventory_repo=ContentInventoryRepository(session),
                    )

                svc = CMSService(
                    connection_repo=CMSConnectionRepository(session),
                    publish_repo=CMSPublishRecordRepository(session),
                    synced_post_repo=CMSSyncedPostRepository(session),
                    storage=storage,
                    fernet_key=fernet_key,
                    inventory_service=inventory_svc,
                )

                connection = await svc.get_connection(company_slug, tenant_id)
                if connection is None:
                    raise RuntimeError("CMS connection not found")

                result = await svc.sync_existing_content(company_slug, connection)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

            # ── Phase 2: Auto-prompt generation for new pages ─────────
            new_page_ids: list[str] = result.get("new_page_ids", [])
            if new_page_ids:
                await _run_auto_prompt_generation(
                    task_id=task_id,
                    company_slug=company_slug,
                    new_page_ids=new_page_ids,
                    session_factory=session_factory,
                    event_bus=event_bus,
                    task_store=task_store,
                    result=result,
                )

            # ── Mark task completed ───────────────────────────────────
            # Strip new_page_ids from the final result (internal use only)
            final_result = {k: v for k, v in result.items() if k != "new_page_ids"}
            task_store.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result=final_result,
            )
            event_bus.publish(task_id, "completed", {"pipeline": "cms_sync", **final_result})

    except asyncio.CancelledError:
        logger.info("CMS sync task %s cancelled", task_id)
    except Exception as exc:
        logger.exception("CMS sync task %s failed: %s", task_id, exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:cms:{company_slug}:*")
        except Exception:
            pass
        task_store.release_slug_lock(f"cms_sync:{company_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()


async def _run_auto_prompt_generation(
    *,
    task_id: str,
    company_slug: str,
    new_page_ids: list[str],
    session_factory: Any,
    event_bus: EventBusProtocol,
    task_store: TaskStoreProtocol,
    result: dict[str, Any],
) -> None:
    """Generate AI visibility prompts for newly discovered pages.

    Called as Phase 2 of ``run_cms_sync_task``.  Opens a fresh DB session,
    creates the orchestrator, and runs prompt generation with
    ``auto_approve=True``.  Failures are logged but never propagate —
    the CMS sync is considered successful regardless.
    """
    from core.config.settings import settings

    cap = settings.auto_prompt_max_pages
    if cap <= 0:
        return

    task_store.update_task(task_id, current_step="prompt_generation")
    event_bus.publish(
        task_id, "step_start",
        {"step": "prompt_generation", "new_page_count": len(new_page_ids)},
    )

    try:
        from core.daily_tracker.content_to_prompt import ContentToPromptService
        from core.daily_tracker.content_to_prompt_orchestrator import (
            ContentToPromptOrchestrator,
        )
        from core.db.repositories.content_inventory_prompt_repo import (
            ContentInventoryPromptRepository,
        )
        from core.db.repositories.content_inventory_repo import (
            ContentInventoryRepository,
        )
        from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
        from core.db.repositories.company_repo import CompanyRepository

        session = session_factory()
        try:
            # Resolve company UUID and brand name
            company_repo = CompanyRepository(session)
            company = await company_repo.get_by_slug(company_slug)
            if company is None:
                logger.warning(
                    "Auto-prompt skipped: company '%s' not found in DB",
                    company_slug,
                )
                return

            company_uuid = company.id
            brand_name = getattr(company, "name", company_slug) or company_slug

            # Cap and convert page IDs
            capped_ids = [uuid.UUID(pid) for pid in new_page_ids[:cap]]
            if len(new_page_ids) > cap:
                logger.info(
                    "Auto-prompt capped at %d pages (total new: %d) for %s",
                    cap, len(new_page_ids), company_slug,
                )

            generator = ContentToPromptService()
            orchestrator = ContentToPromptOrchestrator(
                generator=generator,
                prompt_repo=TrackedPromptRepository(session),
                link_repo=ContentInventoryPromptRepository(session),
                inventory_repo=ContentInventoryRepository(session),
            )

            prompt_result = await orchestrator.run_for_pages(
                company_id=company_slug,
                company_uuid=company_uuid,
                page_ids=capped_ids,
                brand_name=brand_name,
                k=6,
                auto_approve=True,
            )

            await session.commit()

            # Merge prompt results into the sync result dict
            result["prompts_created"] = prompt_result.prompts_created
            result["prompts_deduplicated"] = prompt_result.prompts_deduplicated
            result["prompt_pages_processed"] = prompt_result.pages_processed

            logger.info(
                "Auto-prompt generation complete for %s: %d prompts created, %d deduped",
                company_slug,
                prompt_result.prompts_created,
                prompt_result.prompts_deduplicated,
            )
            event_bus.publish(
                task_id, "step_complete",
                {
                    "step": "prompt_generation",
                    "prompts_created": prompt_result.prompts_created,
                    "prompts_deduplicated": prompt_result.prompts_deduplicated,
                },
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    except Exception as exc:
        logger.exception(
            "Auto-prompt generation failed for %s (sync still succeeded): %s",
            company_slug, exc,
        )
        result["prompt_generation_error"] = str(exc)
        event_bus.publish(
            task_id, "prompt_generation_failed",
            {"error": str(exc)},
        )


async def run_ga4_sync_task(
    task_id: str,
    company_slug: str,
    tenant_id: str,
    task_store: TaskStoreProtocol,
    event_bus: EventBusProtocol,
    session_factory: Any,
    fernet_key: str,
    lookback_days: int = 7,
    start_date_override: str | None = None,
    end_date_override: str | None = None,
) -> None:
    """Background task wrapper for GA4 data sync.

    Creates its own DB session and GA4AnalyticsService instance (the DI session
    from the router is closed by the time the background task runs).
    """
    bind_context(task_id=task_id, pipeline_name="ga4_sync", company_slug=company_slug)
    task_store.update_task(task_id, status=TaskStatus.RUNNING, current_step="sync")
    event_bus.publish(task_id, "pipeline_start", {"pipeline": "ga4_sync"})

    try:
        async with task_store.pipeline_semaphore(task_id):
            from core.analytics.service import GA4AnalyticsService
            from core.config.settings import settings
            from core.db.repositories.analytics_repo import (
                AnalyticsConnectionRepository,
                GA4ConversionEventRepository,
                GA4TrafficDataRepository,
            )

            session = session_factory()
            try:
                svc = GA4AnalyticsService(
                    connection_repo=AnalyticsConnectionRepository(session),
                    traffic_repo=GA4TrafficDataRepository(session),
                    conversion_repo=GA4ConversionEventRepository(session),
                    fernet_key=fernet_key,
                    client_id=settings.google_oauth_client_id or "",
                    client_secret=settings.google_oauth_client_secret or "",
                    redirect_uri=settings.google_oauth_redirect_uri,
                    ai_referral_sources=settings.ai_referral_sources,
                    lookback_days=lookback_days,
                )

                result = await svc.sync_data(
                    company_slug=company_slug,
                    tenant_id=tenant_id,
                    start_date_override=start_date_override,
                    end_date_override=end_date_override,
                )
                await session.commit()

                task_store.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    result=result.model_dump(),
                )
                event_bus.publish(
                    task_id, "completed",
                    {"pipeline": "ga4_sync", **result.model_dump()},
                )
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    except asyncio.CancelledError:
        logger.info("GA4 sync task %s cancelled", task_id)
    except Exception as exc:
        logger.exception("GA4 sync task %s failed: %s", task_id, exc)
        task_store.update_task(
            task_id, status=TaskStatus.FAILED, error=str(exc),
        )
        event_bus.publish(task_id, "failed", {"error": str(exc)})
    finally:
        await task_store.flush_terminal(task_id)
        try:
            _rc = get_sync_redis_or_none()
            if _rc:
                cache_delete_pattern(_rc, f"cache:ga4:{company_slug}:*")
        except Exception:
            pass
        task_store.release_slug_lock(f"ga4_sync:{company_slug}")
        task_store.remove_task_handle(task_id)
        clear_context()
