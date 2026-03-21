"""FastAPI dependency injection helpers."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Optional

import redis.asyncio as aioredis

from fastapi import HTTPException, Request

from api.auth.store import AuthStore
from api.tasks.event_bus import EventBus
from core.auth.json_service import JsonAuthService
from core.auth.service import AuthServiceProtocol
from core.services.brand_data import BrandDataServiceProtocol
from core.services.content_data import ContentDataServiceProtocol
from core.services.gap_data import GapDataServiceProtocol
from core.services.json_brand_data import JsonBrandDataService
from core.services.json_content_data import JsonContentDataService
from core.services.json_gap_data import JsonGapDataService
from core.services.json_kb_data import JsonKBDataService
from core.services.json_persona_data import JsonPersonaDataService
from core.services.json_site_audit_data import JsonSiteAuditDataService
from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService
from core.services.json_vsg_data import JsonVSGDataService
from core.services.kb_data import KBDataServiceProtocol
from core.services.persona_data import PersonaDataServiceProtocol
from core.services.site_audit_data import SiteAuditDataServiceProtocol
from core.services.task_store import TaskStoreProtocol
from core.services.topic_discovery_data import TopicDiscoveryDataServiceProtocol
from core.services.vsg_data import VSGDataServiceProtocol

_logger = logging.getLogger(__name__)


def get_task_store(request: Request) -> TaskStoreProtocol:
    """Return the task store — JSON-backed TaskStore or DbTaskStore.

    Auto-selected at startup in ``app.py._init_task_store()``:
    DbTaskStore when DATABASE_URL is set, else JSON-backed TaskStore.
    """
    return request.app.state.task_store


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_artifacts_root(request: Request) -> Path:
    return request.app.state.artifacts_root


def get_storage_backend(request: Request):
    """Return the app-level StorageBackend (LocalStorageBackend or S3StorageBackend)."""
    return request.app.state.storage_backend


def get_auth_store(request: Request) -> AuthStore:
    return request.app.state.auth_store


def get_redis(request: Request) -> Optional[aioredis.Redis]:
    """Return the Redis client from app state, or None if unavailable."""
    return getattr(request.app.state, "redis", None)


# ── Session-managed helpers ─────────────────────────────────────────
#
# Each ``_build_db_*`` function accepts a pre-created *session* and
# constructs the service from it.  The caller (an async generator)
# owns the session lifecycle so that ``session.close()`` is guaranteed
# even if construction raises.


def _build_db_auth_service(request: Request, session: Any) -> AuthServiceProtocol | None:
    """Construct a DbAuthService from an existing *session*.

    Returns the service or None on import/construction failure.
    """
    try:
        from core.auth.db_service import DbAuthService
        from core.db.repositories.auth_repo import AuthRepository
        from core.db.repositories.company_repo import CompanyRepository
        from core.db.repositories.invite_repo import InviteRepository
        from core.db.repositories.pipeline_defaults_repo import PipelineDefaultsRepository
        from core.db.repositories.product_repo import ProductRepository

        secret_key = getattr(request.app.state, "secret_key", None)
        if secret_key is None:
            return None
        return DbAuthService(
            company_repo=CompanyRepository(session),
            auth_repo=AuthRepository(session),
            invite_repo=InviteRepository(session),
            product_repo=ProductRepository(session),
            defaults_repo=PipelineDefaultsRepository(session),
            secret_key=secret_key,
        )
    except Exception:
        _logger.debug("Failed to build DbAuthService", exc_info=True)
        return None


async def get_auth_service(
    request: Request,
) -> AsyncGenerator[AuthServiceProtocol, None]:
    """Return the auth service with proper DB session lifecycle.

    Priority: pre-built override → DbAuthService (DATABASE_URL) → JsonAuthService.
    DB sessions are committed on success, rolled back on error.
    """
    # 1. Pre-built override (tests, etc.)
    service = getattr(request.app.state, "auth_service", None)
    if service is not None:
        yield service
        return
    # 2. Per-request DB service (when DATABASE_URL is set)
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_auth_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                # Construction failed — close session, fall through to JSON
                await session.close()
                yield JsonAuthService(request.app.state.auth_store)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    # 3. Fallback: JSON-backed
    yield JsonAuthService(request.app.state.auth_store)


def _build_db_gap_data_service(request: Request, session: Any) -> GapDataServiceProtocol | None:
    """Construct a DbGapDataService from an existing *session*."""
    try:
        from core.db.repositories.gap_analysis_repo import GapAnalysisRepository
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.db.repositories.platform_repo import PlatformRepository
        from core.db.repositories.signal_repo import SignalRepository
        from core.services.db_gap_data import DbGapDataService

        return DbGapDataService(
            gap_repo=GapAnalysisRepository(session),
            pipeline_repo=PipelineRepository(session),
            signal_repo=SignalRepository(session),
            platform_repo=PlatformRepository(session),
            artifacts_root=request.app.state.artifacts_root,
        )
    except Exception:
        _logger.debug("Failed to build DbGapDataService", exc_info=True)
        return None


def _build_db_brand_data_service(request: Request, session: Any) -> BrandDataServiceProtocol | None:
    """Construct a DbBrandDataService from an existing *session*."""
    try:
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.services.db_brand_data import DbBrandDataService

        return DbBrandDataService(
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
        )
    except Exception:
        _logger.debug("Failed to build DbBrandDataService", exc_info=True)
        return None


def _build_db_content_data_service(request: Request, session: Any) -> ContentDataServiceProtocol | None:
    """Construct a DbContentDataService from an existing *session*."""
    try:
        from core.db.repositories.content_artifact_repo import ContentArtifactRepository
        from core.db.repositories.content_repo import ContentRepository
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.services.db_content_data import DbContentDataService

        return DbContentDataService(
            content_repo=ContentRepository(session),
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
            artifact_repo=ContentArtifactRepository(session),
        )
    except Exception:
        _logger.debug("Failed to build DbContentDataService", exc_info=True)
        return None


async def get_gap_data_service(
    request: Request,
) -> AsyncGenerator[GapDataServiceProtocol, None]:
    """Return the gap data service with proper DB session lifecycle.

    Checks for a pre-built service on app.state (e.g., from dependency
    override in tests). When db_session_factory is available, constructs
    a per-request FallbackGapDataService (DB first, JSON fallback on 404).
    Otherwise yields JsonGapDataService.
    """
    # 1. Pre-built override (tests, etc.)
    service = getattr(request.app.state, "gap_data_service", None)
    if service is not None:
        yield service
        return

    json_service = JsonGapDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )

    # 2. Per-request DB service with JSON fallback (when DATABASE_URL is set)
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_gap_data_service(request, session)
            if db_service is not None:
                from api.services.fallback_gap_data import FallbackGapDataService
                yield FallbackGapDataService(db=db_service, json=json_service)
                await session.commit()
            else:
                await session.close()
                yield json_service
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return

    # 3. Fallback: filesystem-backed only
    yield json_service


async def get_brand_data_service(
    request: Request,
) -> AsyncGenerator[BrandDataServiceProtocol, None]:
    """Return the brand data service with proper DB session lifecycle.

    Per-request DbBrandDataService when DATABASE_URL set, else JsonBrandDataService.
    """
    service = getattr(request.app.state, "brand_data_service", None)
    if service is not None:
        yield service
        return
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_brand_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonBrandDataService(
                    artifacts_root=request.app.state.artifacts_root,
                    task_store=request.app.state.task_store,
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    yield JsonBrandDataService(
        artifacts_root=request.app.state.artifacts_root,
        task_store=request.app.state.task_store,
    )


async def get_content_data_service(
    request: Request,
) -> AsyncGenerator[ContentDataServiceProtocol, None]:
    """Return the content data service with proper DB session lifecycle.

    Per-request DbContentDataService when DATABASE_URL set, else JsonContentDataService.
    """
    service = getattr(request.app.state, "content_data_service", None)
    if service is not None:
        yield service
        return
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_content_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonContentDataService(
                    artifacts_root=request.app.state.artifacts_root,
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    yield JsonContentDataService(
        artifacts_root=request.app.state.artifacts_root,
    )


def _build_db_site_audit_data_service(
    request: Request, session: Any,
) -> SiteAuditDataServiceProtocol | None:
    """Construct a DbSiteAuditDataService from an existing *session*."""
    try:
        from core.db.repositories.company_repo import CompanyRepository
        from core.db.repositories.site_audit_repo import SiteAuditRepository
        from core.services.db_site_audit_data import DbSiteAuditDataService

        return DbSiteAuditDataService(
            audit_repo=SiteAuditRepository(session),
            company_repo=CompanyRepository(session),
            artifacts_root=request.app.state.artifacts_root,
        )
    except Exception:
        _logger.debug("Failed to build DbSiteAuditDataService", exc_info=True)
        return None


async def get_site_audit_data_service(
    request: Request,
) -> AsyncGenerator[SiteAuditDataServiceProtocol, None]:
    """Return the site audit data service with proper DB session lifecycle.

    Priority: pre-built override → DbSiteAuditDataService (DATABASE_URL) →
    JsonSiteAuditDataService.
    """
    # 1. Pre-built override (tests, etc.)
    service = getattr(request.app.state, "site_audit_data_service", None)
    if service is not None:
        yield service
        return
    # 2. Per-request DB service (when DATABASE_URL is set)
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_site_audit_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonSiteAuditDataService(
                    artifacts_root=request.app.state.artifacts_root,
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    # 3. Fallback: filesystem-backed
    yield JsonSiteAuditDataService(
        artifacts_root=request.app.state.artifacts_root,
    )


# ── KB Data Service ──────────────────────────────────────────────────


def _build_db_kb_data_service(request: Request, session: Any) -> KBDataServiceProtocol | None:
    """Construct a DbKBDataService from an existing *session*."""
    try:
        from core.db.repositories.kb_repo import (
            KBDocumentRepository,
            KBRunRepository,
            KBSynthesisRepository,
        )
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.services.db_kb_data import DbKBDataService

        return DbKBDataService(
            kb_run_repo=KBRunRepository(session),
            kb_doc_repo=KBDocumentRepository(session),
            kb_synth_repo=KBSynthesisRepository(session),
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
            backend=getattr(request.app.state, "storage_backend", None),
        )
    except Exception:
        _logger.debug("Failed to build DbKBDataService", exc_info=True)
        return None


async def get_kb_data_service(
    request: Request,
) -> AsyncGenerator[KBDataServiceProtocol, None]:
    """Return the KB data service with proper DB session lifecycle.

    Priority: pre-built override → DbKBDataService (DATABASE_URL) → JsonKBDataService.
    """
    service = getattr(request.app.state, "kb_data_service", None)
    if service is not None:
        yield service
        return
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_kb_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonKBDataService(
                    artifacts_root=request.app.state.artifacts_root,
                    backend=getattr(request.app.state, "storage_backend", None),
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    yield JsonKBDataService(
        artifacts_root=request.app.state.artifacts_root,
        backend=getattr(request.app.state, "storage_backend", None),
    )


# ── Persona Data Service ────────────────────────────────────────────


def _build_db_persona_data_service(request: Request, session: Any) -> PersonaDataServiceProtocol | None:
    """Construct a DbPersonaDataService from an existing *session*."""
    try:
        from core.db.repositories.persona_repo import (
            PersonaProfileRepository,
            PersonaRunRepository,
        )
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.services.db_persona_data import DbPersonaDataService

        return DbPersonaDataService(
            persona_run_repo=PersonaRunRepository(session),
            persona_profile_repo=PersonaProfileRepository(session),
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
            backend=getattr(request.app.state, "storage_backend", None),
        )
    except Exception:
        _logger.debug("Failed to build DbPersonaDataService", exc_info=True)
        return None


async def get_persona_data_service(
    request: Request,
) -> AsyncGenerator[PersonaDataServiceProtocol, None]:
    """Return the persona data service with proper DB session lifecycle.

    Priority: pre-built override → DbPersonaDataService (DATABASE_URL) → JsonPersonaDataService.
    """
    service = getattr(request.app.state, "persona_data_service", None)
    if service is not None:
        yield service
        return
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_persona_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonPersonaDataService(
                    artifacts_root=request.app.state.artifacts_root,
                    backend=getattr(request.app.state, "storage_backend", None),
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    yield JsonPersonaDataService(
        artifacts_root=request.app.state.artifacts_root,
        backend=getattr(request.app.state, "storage_backend", None),
    )


# ── VSG Data Service ────────────────────────────────────────────────


def _build_db_vsg_data_service(request: Request, session: Any) -> VSGDataServiceProtocol | None:
    """Construct a DbVSGDataService from an existing *session*."""
    try:
        from core.db.repositories.pipeline_repo import PipelineRepository
        from core.db.repositories.vsg_repo import (
            VSGAuthorRepository,
            VSGGuideRepository,
            VSGRunRepository,
        )
        from core.services.db_vsg_data import DbVSGDataService

        return DbVSGDataService(
            vsg_run_repo=VSGRunRepository(session),
            vsg_author_repo=VSGAuthorRepository(session),
            vsg_guide_repo=VSGGuideRepository(session),
            pipeline_repo=PipelineRepository(session),
            artifacts_root=request.app.state.artifacts_root,
            backend=getattr(request.app.state, "storage_backend", None),
        )
    except Exception:
        _logger.debug("Failed to build DbVSGDataService", exc_info=True)
        return None


async def get_vsg_data_service(
    request: Request,
) -> AsyncGenerator[VSGDataServiceProtocol, None]:
    """Return the VSG data service with proper DB session lifecycle.

    Priority: pre-built override → DbVSGDataService (DATABASE_URL) → JsonVSGDataService.
    """
    service = getattr(request.app.state, "vsg_data_service", None)
    if service is not None:
        yield service
        return
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_vsg_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonVSGDataService(
                    artifacts_root=request.app.state.artifacts_root,
                    backend=getattr(request.app.state, "storage_backend", None),
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    yield JsonVSGDataService(
        artifacts_root=request.app.state.artifacts_root,
        backend=getattr(request.app.state, "storage_backend", None),
    )


# ── TD Data Service ─────────────────────────────────────────────────


def _build_db_td_data_service(request: Request, session: Any) -> TopicDiscoveryDataServiceProtocol | None:
    """Construct a DbTopicDiscoveryDataService from an existing *session*."""
    try:
        from core.db.repositories.topic_discovery_repo import (
            PersonaAffinityRepository,
            SourceResultRepository,
            SubdomainNodeRepository,
            TopicAssignmentRepository,
            TaxonomyTreeRepository,
            TopicDiscoveryRepository,
        )
        from core.services.db_topic_discovery_data import DbTopicDiscoveryDataService

        return DbTopicDiscoveryDataService(
            td_repo=TopicDiscoveryRepository(session),
            taxonomy_repo=TaxonomyTreeRepository(session),
            assignment_repo=TopicAssignmentRepository(session),
            artifacts_root=request.app.state.artifacts_root,
            node_repo=SubdomainNodeRepository(session),
            source_result_repo=SourceResultRepository(session),
            persona_affinity_repo=PersonaAffinityRepository(session),
            backend=getattr(request.app.state, "storage_backend", None),
        )
    except Exception:
        _logger.debug("Failed to build DbTopicDiscoveryDataService", exc_info=True)
        return None


async def get_td_data_service(
    request: Request,
) -> AsyncGenerator[TopicDiscoveryDataServiceProtocol, None]:
    """Return the TD data service with proper DB session lifecycle.

    Priority: pre-built override → DbTopicDiscoveryDataService (DATABASE_URL) →
    JsonTopicDiscoveryDataService.
    """
    service = getattr(request.app.state, "td_data_service", None)
    if service is not None:
        yield service
        return
    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            db_service = _build_db_td_data_service(request, session)
            if db_service is not None:
                yield db_service
                await session.commit()
            else:
                await session.close()
                yield JsonTopicDiscoveryDataService(
                    artifacts_root=request.app.state.artifacts_root,
                    backend=getattr(request.app.state, "storage_backend", None),
                )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return
    yield JsonTopicDiscoveryDataService(
        artifacts_root=request.app.state.artifacts_root,
        backend=getattr(request.app.state, "storage_backend", None),
    )


# ── Daily Tracker dependencies ───────────────────────────────────────


async def get_prompt_library_service(request: Request) -> AsyncGenerator[Any, None]:
    """Return the PromptLibraryService for daily tracker prompt CRUD.

    Checks for a pre-built override on app.state (tests), then constructs
    a new instance with proper session lifecycle (commit/rollback/close).
    """
    service = getattr(request.app.state, "prompt_library_service", None)
    if service is not None:
        yield service
        return

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
            from core.daily_tracker.prompt_library import PromptLibraryService

            svc = PromptLibraryService(prompt_repo=TrackedPromptRepository(session))
            yield svc
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return

    raise HTTPException(
        status_code=503,
        detail="Prompt library service unavailable (requires DATABASE_URL)",
    )


async def get_analytics_service(request: Request) -> AsyncGenerator[Any, None]:
    """Return the AnalyticsService for daily tracker analytics.

    Checks for a pre-built override on app.state (tests), then constructs
    a new instance with proper DB session lifecycle.
    """
    service = getattr(request.app.state, "analytics_service", None)
    if service is not None:
        yield service
        return

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            from core.daily_tracker.analytics_engine import AnalyticsService
            from core.db.repositories.daily_tracker_repo import (
                DailyRunRepository,
                DailyRunResponseRepository,
            )

            response_repo = DailyRunResponseRepository(session)
            run_repo = DailyRunRepository(session)
            provider = _DbResponseDataProvider(response_repo, run_repo)
            svc = AnalyticsService(data_provider=provider)
            yield svc
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return

    raise HTTPException(
        status_code=503,
        detail="Analytics service unavailable (requires DATABASE_URL)",
    )


async def get_daily_tracker_orchestrator(request: Request) -> AsyncGenerator[Any, None]:
    """Return the DailyTrackerOrchestrator for running daily tracking.

    Checks for a pre-built override on app.state (tests), then constructs
    a new instance with proper session lifecycle (commit/rollback/close).
    """
    service = getattr(request.app.state, "daily_tracker_orchestrator", None)
    if service is not None:
        yield service
        return

    sf = getattr(request.app.state, "db_session_factory", None)
    if sf is not None:
        session = sf()
        try:
            from core.db.repositories.daily_tracker_repo import TrackedPromptRepository
            from core.daily_tracker.prompt_library import PromptLibraryService
            from core.daily_tracker.platform_runner import PlatformRunnerService
            from core.daily_tracker.mention_detector import MentionDetector
            from core.daily_tracker.orchestrator import DailyTrackerOrchestrator

            prompt_repo = TrackedPromptRepository(session)
            svc = DailyTrackerOrchestrator(
                prompt_service=PromptLibraryService(prompt_repo=prompt_repo),
                runner_service=PlatformRunnerService(),
                mention_detector=MentionDetector(),
            )
            yield svc
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
        return

    raise HTTPException(
        status_code=503,
        detail="Daily tracker orchestrator unavailable (requires DATABASE_URL)",
    )


# ── Daily Tracker internal helpers ───────────────────────────────────


class _DbResponseDataProvider:
    """Adapter between DB repos and the AnalyticsService ResponseDataProvider protocol.

    Why: AnalyticsService depends on a ResponseDataProvider protocol, not directly
    on DB repos.  This adapter bridges the gap in the DI layer so the analytics
    engine remains testable with pure mocks.
    """

    def __init__(self, response_repo: Any, run_repo: Any) -> None:
        self._response_repo = response_repo
        self._run_repo = run_repo

    async def get_responses_for_run(
        self, run_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all platform responses for a run, converting ORM to dicts."""
        import uuid as _uuid

        rows = await self._response_repo.get_responses_by_run(
            _uuid.UUID(run_id)
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_responses_for_company(
        self, company_id: str, *, days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch responses for a company's recent runs."""
        runs = await self._run_repo.list_runs(company_id, limit=100)
        all_responses: list[dict[str, Any]] = []
        for run in runs:
            rows = await self._response_repo.get_responses_by_run(run.id)
            all_responses.extend(self._row_to_dict(r) for r in rows)
        return all_responses

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert an ORM DailyRunResponseModel to a response dict."""
        return {
            "prompt_id": str(row.prompt_id),
            "engine": row.engine,
            "response_text": row.response_text,
            "mention_analysis": {
                "brand_mentioned": row.brand_mentioned,
                "brand_mention_count": row.brand_mention_count,
                "competitor_mentions": row.competitor_mentions or {},
                "citations": row.citations or [],
                "citation_rank": row.citation_rank,
            },
        }
