"""Aggregates workspace profile data for dashboard shell and legacy company routes."""
from __future__ import annotations

import uuid as _uuid
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.workspace import (
    Workspace,
    WorkspaceArtifactStatus,
    WorkspaceContentStudioSummary,
    WorkspaceIntegrationsSummary,
    WorkspaceMembership,
    WorkspaceProductSummary,
    WorkspaceProfile,
    WorkspaceResearchSummary,
    WorkspaceRunningTaskSummary,
    WorkspaceStatsSummary,
    WorkspaceTopicDiscoverySummary,
)
from core.services.company_profile_helpers import (
    build_research_summary,
    detect_artifact_status,
    detect_personas,
    get_latest_runs,
    get_running_tasks,
    has_nested_artifacts,
)
from core.services.task_store import TaskStoreProtocol


class WorkspaceProfileService:
    """Builds the full workspace profile snapshot used by API and frontend."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_profile(
        self,
        workspace_slug: str,
        *,
        workspace: Workspace,
        membership: WorkspaceMembership,
        auth_service: Any = None,
        artifacts_root: Path | None = None,
        storage_backend: Any = None,
        task_store: TaskStoreProtocol | None = None,
    ) -> WorkspaceProfile:
        company = None
        if auth_service is not None:
            company = await auth_service.get_company_by_slug(workspace_slug)

        products: List[WorkspaceProductSummary] = []
        if company and company.products:
            for product in company.products:
                effective = f"{workspace_slug}__{product.slug}"
                products.append(
                    WorkspaceProductSummary(
                        slug=product.slug,
                        name=product.name,
                        domain=product.domain,
                        description=product.description,
                        has_research=(
                            detect_artifact_status(
                                artifacts_root or Path("."),
                                "company_context",
                                effective,
                                backend=storage_backend,
                            )
                            != "none"
                            if artifacts_root
                            else False
                        ),
                        has_gap_analysis=(
                            has_nested_artifacts(
                                artifacts_root or Path("."),
                                "gap_analysis",
                                effective,
                                backend=storage_backend,
                            )
                            if artifacts_root
                            else False
                        ),
                        has_content=(
                            has_nested_artifacts(
                                artifacts_root or Path("."),
                                "content",
                                effective,
                                backend=storage_backend,
                            )
                            if artifacts_root
                            else False
                        ),
                    )
                )

        research_raw = (
            build_research_summary(
                artifacts_root, workspace_slug, backend=storage_backend
            )
            if artifacts_root
            else {}
        )
        research_summary = WorkspaceResearchSummary(**research_raw)

        has_research = (
            research_summary.company_context_status != "none"
            or len(research_summary.personas) > 0
            or research_summary.style_guide_status != "none"
        )
        has_gap_analysis = (
            has_nested_artifacts(
                artifacts_root or Path("."),
                "gap_analysis",
                workspace_slug,
                backend=storage_backend,
            )
            if artifacts_root
            else False
        )
        has_content = (
            has_nested_artifacts(
                artifacts_root or Path("."),
                "content",
                workspace_slug,
                backend=storage_backend,
            )
            if artifacts_root
            else False
        )

        artifact_status = self._build_artifact_status(
            workspace_slug,
            research_summary,
            has_gap_analysis,
            has_content,
            artifacts_root,
            storage_backend,
            task_store,
        )

        integrations = await self._build_integrations(workspace)
        stats = await self._build_stats(workspace)
        topic_discovery = await self._build_topic_discovery(workspace_slug, task_store)
        content_studio = await self._build_content_studio(workspace_slug)

        latest_runs_raw = (
            get_latest_runs(task_store, workspace_slug) if task_store else {}
        )
        latest_runs = {
            key: value for key, value in latest_runs_raw.items() if value is not None
        }

        running_tasks_raw = (
            get_running_tasks(task_store, workspace_slug) if task_store else []
        )
        running_tasks = [
            WorkspaceRunningTaskSummary(**item) for item in running_tasks_raw
        ]

        return WorkspaceProfile(
            id=workspace.id,
            slug=workspace.slug,
            name=workspace.name,
            primary_domain=workspace.primary_domain,
            additional_domains=workspace.additional_domains,
            industry=workspace.industry,
            color=workspace.color,
            logo_url=workspace.logo_url,
            role=membership.role,
            is_archived=workspace.is_archived,
            products=products,
            integrations=integrations,
            artifact_status=artifact_status,
            has_research=has_research,
            has_gap_analysis=has_gap_analysis,
            has_content=has_content,
            research_summary=research_summary,
            latest_runs=latest_runs,
            running_tasks=running_tasks,
            stats=stats,
            topic_discovery=topic_discovery,
            content_studio=content_studio,
        )

    def _build_artifact_status(
        self,
        workspace_slug: str,
        research_summary: WorkspaceResearchSummary,
        has_gap_analysis: bool,
        has_content: bool,
        artifacts_root: Path | None,
        storage_backend: Any,
        task_store: TaskStoreProtocol | None,
    ) -> WorkspaceArtifactStatus:
        status = WorkspaceArtifactStatus()
        if research_summary.company_context_status != "none":
            status.knowledge_base = research_summary.company_context_status
        if research_summary.personas:
            status.audience_personas = "ready"
        if research_summary.style_guide_status != "none":
            status.voice_style_guide = research_summary.style_guide_status
        if has_gap_analysis:
            status.gap_analysis = "ready"
        if has_content:
            status.content_engine = "ready"

        if task_store is not None:
            for task in task_store.list_tasks():
                if task.company_slug != workspace_slug:
                    continue
                if task.status.value not in (
                    "pending",
                    "running",
                    "PENDING",
                    "RUNNING",
                    "pending_approval",
                ):
                    continue
                pipeline = task.pipeline
                if pipeline in ("gap_analysis", "td_gap_analysis"):
                    status.gap_analysis = "running"
                elif pipeline in ("content", "content_v13", "td_content"):
                    status.content_engine = "running"
                elif pipeline == "topic_discovery":
                    status.topic_discovery = "running"

        return status

    async def _build_integrations(self, workspace: Workspace) -> WorkspaceIntegrationsSummary:
        integrations = WorkspaceIntegrationsSummary()
        cid = _uuid.UUID(workspace.company_id)

        try:
            from core.db.models.cms import CMSConnectionModel

            stmt = (
                select(CMSConnectionModel)
                .where(
                    CMSConnectionModel.company_id == cid,
                    CMSConnectionModel.is_active.is_(True),
                )
                .limit(1)
            )
            result = await self._session.execute(stmt)
            cms = result.scalar_one_or_none()
            if cms is not None:
                integrations.cms = {
                    "connected": True,
                    "provider": cms.provider.value
                    if hasattr(cms.provider, "value")
                    else str(cms.provider),
                }
        except Exception:
            pass

        try:
            from core.db.models.analytics import AnalyticsConnectionModel

            stmt = (
                select(AnalyticsConnectionModel)
                .where(
                    AnalyticsConnectionModel.company_id == cid,
                    AnalyticsConnectionModel.is_active.is_(True),
                )
                .limit(1)
            )
            result = await self._session.execute(stmt)
            ga4 = result.scalar_one_or_none()
            if ga4 is not None:
                integrations.ga4 = {
                    "connected": True,
                    "provider": ga4.provider.value
                    if hasattr(ga4.provider, "value")
                    else str(ga4.provider),
                    "property_id": ga4.ga4_property_id or "",
                    "property_name": ga4.ga4_property_name or "",
                }
        except Exception:
            pass

        return integrations

    async def _build_stats(self, workspace: Workspace) -> WorkspaceStatsSummary:
        stats = WorkspaceStatsSummary()
        cid = _uuid.UUID(workspace.company_id)
        company_id_str = str(workspace.company_id)

        try:
            from core.db.models.content_inventory import ContentInventoryModel

            stmt = select(func.count()).select_from(ContentInventoryModel).where(
                ContentInventoryModel.company_id == cid
            )
            result = await self._session.execute(stmt)
            stats.content_inventory_count = int(result.scalar() or 0)
        except Exception:
            pass

        try:
            from core.db.models.daily_tracker import TrackedPromptModel

            total_stmt = select(func.count()).select_from(TrackedPromptModel).where(
                TrackedPromptModel.company_id == company_id_str
            )
            active_stmt = select(func.count()).select_from(TrackedPromptModel).where(
                TrackedPromptModel.company_id == company_id_str,
                TrackedPromptModel.active.is_(True),
            )
            stats.tracked_prompts_total = int(
                (await self._session.execute(total_stmt)).scalar() or 0
            )
            stats.tracked_prompts_active = int(
                (await self._session.execute(active_stmt)).scalar() or 0
            )
        except Exception:
            pass

        try:
            from core.db.models.knowledge_docs import KnowledgeDocumentModel

            stmt = select(func.count()).select_from(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.company_id == cid
            )
            result = await self._session.execute(stmt)
            stats.knowledge_docs_count = int(result.scalar() or 0)
        except Exception:
            pass

        return stats

    async def _build_topic_discovery(
        self,
        workspace_slug: str,
        task_store: TaskStoreProtocol | None,
    ) -> WorkspaceTopicDiscoverySummary:
        summary = WorkspaceTopicDiscoverySummary()
        try:
            from core.db.models.topic_discovery import (
                TopicAssignmentModel,
                TopicDiscoveryModel,
            )

            slug_filter = or_(
                TopicDiscoveryModel.effective_slug == workspace_slug,
                TopicDiscoveryModel.effective_slug.like(f"{workspace_slug}__%"),
            )
            latest_stmt = (
                select(TopicDiscoveryModel)
                .where(slug_filter)
                .order_by(TopicDiscoveryModel.created_at.desc())
                .limit(1)
            )
            result = await self._session.execute(latest_stmt)
            latest = result.scalar_one_or_none()
            if latest is not None:
                summary.latest_run_id = str(latest.id)
                summary.status = (
                    latest.status.value
                    if hasattr(latest.status, "value")
                    else str(latest.status)
                )

            count_stmt = (
                select(func.count())
                .select_from(TopicAssignmentModel)
                .join(
                    TopicDiscoveryModel,
                    TopicAssignmentModel.discovery_id == TopicDiscoveryModel.id,
                )
                .where(slug_filter)
            )
            count_result = await self._session.execute(count_stmt)
            summary.assignment_count = int(count_result.scalar() or 0)
        except Exception:
            pass

        if task_store is not None:
            for task in task_store.list_tasks():
                if task.company_slug != workspace_slug:
                    continue
                if task.pipeline == "topic_discovery" and task.status.value in (
                    "pending",
                    "running",
                    "pending_approval",
                ):
                    summary.status = "running"
                    break

        return summary

    async def _build_content_studio(
        self, workspace_slug: str
    ) -> WorkspaceContentStudioSummary:
        summary = WorkspaceContentStudioSummary()
        try:
            from core.db.models.content_engine_runs import ContentEngineTopicRunModel

            slug_filter = or_(
                ContentEngineTopicRunModel.effective_slug == workspace_slug,
                ContentEngineTopicRunModel.effective_slug.like(f"{workspace_slug}__%"),
            )
            stmt = (
                select(
                    ContentEngineTopicRunModel.status,
                    func.count(),
                )
                .where(slug_filter)
                .group_by(ContentEngineTopicRunModel.status)
            )
            result = await self._session.execute(stmt)
            for status, count in result.all():
                value = int(count or 0)
                normalized = str(status).lower()
                if normalized in ("content_queued", "queued", "resume_queued"):
                    summary.queued += value
                elif normalized in ("running", "claimed"):
                    summary.running += value
                elif normalized in ("waiting_human",):
                    summary.waiting_human += value
                elif normalized in ("completed", "published"):
                    summary.completed += value
                elif normalized in ("failed", "cancelled"):
                    summary.failed += value
        except Exception:
            pass

        return summary
