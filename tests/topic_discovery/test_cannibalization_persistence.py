from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_inventory.models import CannibalizationMatch
from core.models.topic_discovery import TopicAssignment


def _make_session_factory():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = ctx
    return factory, session


def _make_assignment(**overrides) -> TopicAssignment:
    return TopicAssignment(
        id=str(overrides.get("id", uuid.uuid4())),
        topic_text=overrides.get("topic_text", "AI content strategy guide"),
        metadata=overrides.get(
            "metadata",
            {
                "cannibalization_risk": 0.91,
                "cannibalization_risk_score": 0.89,
                "cannibalization_risk_level": "high",
                "cannibalization_recommended_action": "merge_or_refresh_existing",
                "cannibalization_reasons": ["Existing page already covers this angle."],
                "cannibalization_matches": [
                    {
                        "inventory_id": str(uuid.uuid4()),
                        "url": "https://example.com/existing-guide",
                        "title": "Existing Guide",
                        "similarity": 0.91,
                        "risk_score": 0.89,
                        "risk_level": "high",
                        "reasons": ["Very similar"],
                        "signals": {
                            "semantic_similarity": 0.91,
                            "query_overlap": 0.5,
                        },
                    }
                ],
            },
        ),
    )


class TestPersistAssignmentCannibalizationSnapshots:
    async def test_persists_durable_rows_and_metadata_mirror(self):
        from core.topic_discovery.cannibalization_service import (
            persist_assignment_cannibalization_snapshots,
        )

        session_factory, session = _make_session_factory()
        discovery_id = uuid.uuid4()
        company_id = uuid.uuid4()
        assignment = _make_assignment()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignmentRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentCannibalizationRepository"
        ) as MockCannRepo:
            MockAssignmentRepo.return_value.bulk_merge_metadata = AsyncMock(return_value=1)
            MockCannRepo.return_value.bulk_upsert_assessments = AsyncMock(return_value=1)

            count = await persist_assignment_cannibalization_snapshots(
                session_factory,
                company_id=company_id,
                discovery_id=discovery_id,
                assignments=[assignment],
                source="topic_expansion_pipeline",
                matrix_version=3,
            )

        assert count == 1
        session.commit.assert_awaited_once()
        MockAssignmentRepo.return_value.bulk_merge_metadata.assert_awaited_once()
        MockCannRepo.return_value.bulk_upsert_assessments.assert_awaited_once()

        persisted_record = (
            MockCannRepo.return_value.bulk_upsert_assessments.await_args.args[0][0]
        )
        assert persisted_record["assignment_id"] == uuid.UUID(assignment.id)
        assert persisted_record["discovery_id"] == discovery_id
        assert persisted_record["company_id"] == company_id
        assert persisted_record["risk_level"] == "high"
        assert persisted_record["top_match_inventory_id"] is not None
        assert persisted_record["metadata_json"]["source"] == "topic_expansion_pipeline"
        assert persisted_record["metadata_json"]["matrix_version"] == 3


class TestRecalculateAssignmentCannibalizationRecords:
    async def test_recalculates_from_db_and_persists(self):
        from core.topic_discovery.cannibalization_service import (
            build_assignment_similarity_query,
            recalculate_assignment_cannibalization_records,
        )

        discovery_id = uuid.uuid4()
        company_id = uuid.uuid4()
        assignment_id = uuid.uuid4()
        inventory_id = uuid.uuid4()

        session_factory, _session = _make_session_factory()
        db_row = MagicMock()
        db_row.id = assignment_id

        assignment = _make_assignment(id=assignment_id, metadata={"target_keywords": ["AI content strategy"]})
        query_text = build_assignment_similarity_query(assignment)
        match = CannibalizationMatch(
            inventory_id=str(inventory_id),
            url="https://example.com/existing-guide",
            title="Existing Guide",
            similarity=0.88,
            word_count=1200,
            content_preview="Preview",
            content_type_detected="blog_post",
        )

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignmentRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentCannibalizationRepository"
        ) as MockCannRepo, patch(
            "core.db.repositories.content_inventory_prompt_repo.ContentInventoryPromptRepository"
        ) as MockPromptRepo, patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository"
        ) as MockInventoryRepo, patch(
            "core.services.content_inventory_service.ContentInventoryService"
        ) as MockInventoryService, patch(
            "core.topic_discovery.cannibalization_service._db_row_to_pydantic_assignment",
            return_value=assignment,
        ):
            MockAssignmentRepo.return_value.list_for_cannibalization = AsyncMock(
                side_effect=[[db_row], [db_row]],
            )
            MockAssignmentRepo.return_value.bulk_merge_metadata = AsyncMock(return_value=1)
            MockCannRepo.return_value.bulk_upsert_assessments = AsyncMock(return_value=1)
            MockPromptRepo.return_value.get_citation_metrics_batch = AsyncMock(
                return_value=[{"inventory_id": inventory_id, "total_cited": 2}],
            )
            MockPromptRepo.return_value.get_page_prompt_scopes_batch = AsyncMock(
                return_value={
                    inventory_id: {
                        "root_prompt_ids": [uuid.uuid4()],
                        "prompt_ids": [uuid.uuid4()],
                        "fanout_prompt_ids": [],
                        "prompt_texts": ["AI content strategy for finance teams"],
                    }
                },
            )
            MockInventoryService.return_value.check_cannibalization_batch = AsyncMock(
                return_value={query_text: [match]},
            )

            count = await recalculate_assignment_cannibalization_records(
                session_factory,
                company_id=company_id,
                discovery_id=discovery_id,
                matrix_version=4,
                source="td_matrix_persist",
            )

        assert count == 1
        MockInventoryService.return_value.check_cannibalization_batch.assert_awaited_once()
        MockCannRepo.return_value.bulk_upsert_assessments.assert_awaited_once()
        MockAssignmentRepo.return_value.bulk_merge_metadata.assert_awaited_once()
        MockPromptRepo.return_value.get_page_prompt_scopes_batch.assert_awaited_once()

    async def test_recalculates_only_requested_assignment_ids(self):
        from core.topic_discovery.cannibalization_service import (
            build_assignment_similarity_query,
            recalculate_assignment_cannibalization_records,
        )

        discovery_id = uuid.uuid4()
        company_id = uuid.uuid4()
        assignment_id = uuid.uuid4()
        inventory_id = uuid.uuid4()

        session_factory, _session = _make_session_factory()
        db_row = MagicMock()
        db_row.id = assignment_id

        assignment = _make_assignment(
            id=assignment_id,
            metadata={"target_keywords": ["AI content strategy"]},
        )
        query_text = build_assignment_similarity_query(assignment)
        match = CannibalizationMatch(
            inventory_id=str(inventory_id),
            url="https://example.com/existing-guide",
            title="Existing Guide",
            similarity=0.88,
            word_count=1200,
            content_preview="Preview",
            content_type_detected="blog_post",
        )

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignmentRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentCannibalizationRepository"
        ) as MockCannRepo, patch(
            "core.db.repositories.content_inventory_prompt_repo.ContentInventoryPromptRepository"
        ) as MockPromptRepo, patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository"
        ), patch(
            "core.services.content_inventory_service.ContentInventoryService"
        ) as MockInventoryService, patch(
            "core.topic_discovery.cannibalization_service._db_row_to_pydantic_assignment",
            return_value=assignment,
        ):
            MockAssignmentRepo.return_value.list_for_cannibalization = AsyncMock(
                side_effect=[[db_row], [db_row]],
            )
            MockAssignmentRepo.return_value.bulk_merge_metadata = AsyncMock(return_value=1)
            MockCannRepo.return_value.bulk_upsert_assessments = AsyncMock(return_value=1)
            MockPromptRepo.return_value.get_citation_metrics_batch = AsyncMock(
                return_value=[{"inventory_id": inventory_id, "total_cited": 2}],
            )
            MockPromptRepo.return_value.get_page_prompt_scopes_batch = AsyncMock(
                return_value={
                    inventory_id: {
                        "root_prompt_ids": [uuid.uuid4()],
                        "prompt_ids": [uuid.uuid4()],
                        "fanout_prompt_ids": [],
                        "prompt_texts": ["AI content strategy for finance teams"],
                    }
                },
            )
            MockInventoryService.return_value.check_cannibalization_batch = AsyncMock(
                return_value={query_text: [match]},
            )

            await recalculate_assignment_cannibalization_records(
                session_factory,
                company_id=company_id,
                discovery_id=discovery_id,
                assignment_ids=[assignment_id],
                source="td_delta_recompute",
            )

        list_kwargs = MockAssignmentRepo.return_value.list_for_cannibalization.await_args.kwargs
        assert list_kwargs["assignment_ids"] == [assignment_id]


class TestResolveImpactedAssignmentScopeForInventoryChanges:
    async def test_unions_existing_top_matches_with_latest_planner_assignments(self):
        from core.topic_discovery.cannibalization_service import (
            resolve_impacted_assignment_scope_for_inventory_changes,
        )

        discovery_id = uuid.uuid4()
        company_id = uuid.uuid4()
        page_id = uuid.uuid4()
        existing_assignment_id = uuid.uuid4()
        planner_assignment_id = uuid.uuid4()

        session_factory, _session = _make_session_factory()
        latest_discovery = MagicMock()
        latest_discovery.id = discovery_id
        latest_discovery.matrix_version = 7

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscoveryRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentCannibalizationRepository"
        ) as MockCannRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignmentRepo:
            MockDiscoveryRepo.return_value.get_latest_by_company = AsyncMock(
                return_value=latest_discovery,
            )
            MockCannRepo.return_value.get_assignment_ids_by_top_match_inventory_ids = AsyncMock(
                return_value=[existing_assignment_id],
            )
            MockAssignmentRepo.return_value.list_delta_recompute_assignment_ids = AsyncMock(
                return_value=[planner_assignment_id],
            )

            resolved_discovery_id, assignment_ids = (
                await resolve_impacted_assignment_scope_for_inventory_changes(
                    session_factory,
                    company_id=company_id,
                    inventory_ids=[page_id],
                    assignment_cap=25,
                )
            )

        assert resolved_discovery_id == discovery_id
        assert assignment_ids == [existing_assignment_id, planner_assignment_id]
        MockAssignmentRepo.return_value.list_delta_recompute_assignment_ids.assert_awaited_once_with(
            discovery_id,
            matrix_version=7,
            limit=25,
        )


class TestPersistHooksWireCannibalization:
    async def test_persist_td_assignments_triggers_recalculation(self):
        from core.topic_discovery.persistence import persist_td_assignments

        session_factory, session = _make_session_factory()
        discovery_id = uuid.uuid4()
        company_id = uuid.uuid4()
        matrix = SimpleNamespace(
            assignments=[_make_assignment()],
            total_assignments=1,
        )

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.db.repositories.topic_discovery_repo.TopicDiscoveryRepository"
        ) as MockDiscRepo, patch(
            "core.topic_discovery.cannibalization_service.recalculate_assignment_cannibalization_records",
            new_callable=AsyncMock,
        ) as mock_recalc:
            MockAssignRepo.return_value.delete_by_discovery = AsyncMock(return_value=0)
            MockAssignRepo.return_value.bulk_create = AsyncMock(return_value=[])
            MockDiscRepo.return_value.update_versions = AsyncMock(return_value=None)

            await persist_td_assignments(
                session_factory,
                uuid.uuid4(),
                company_id,
                discovery_id,
                matrix,
                7,
            )

        session.commit.assert_awaited_once()
        mock_recalc.assert_awaited_once()
        assert mock_recalc.await_args.kwargs["matrix_version"] == 7
        assert mock_recalc.await_args.kwargs["source"] == "td_matrix_persist"

    async def test_db_write_assignments_for_subdomain_persists_snapshot(self):
        from core.topic_discovery.db_ops import db_write_assignments_for_subdomain

        session_factory, session = _make_session_factory()
        discovery_id = uuid.uuid4()
        company_id = uuid.uuid4()
        subdomain_id = uuid.uuid4()
        expansion_batch_id = uuid.uuid4()

        assignment = _make_assignment()

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository"
        ) as MockAssignRepo, patch(
            "core.topic_discovery.cannibalization_service.persist_assignment_cannibalization_snapshots",
            new_callable=AsyncMock,
        ) as mock_persist, patch(
            "core.topic_discovery.display_id.backfill_display_ids",
            new_callable=AsyncMock,
        ) as mock_backfill:
            MockAssignRepo.return_value.delete_by_subdomain = AsyncMock(return_value=0)
            MockAssignRepo.return_value.insert_for_subdomain = AsyncMock(return_value=1)

            count = await db_write_assignments_for_subdomain(
                session_factory,
                discovery_id,
                subdomain_id,
                [assignment],
                5,
                expansion_batch_id,
                company_id=company_id,
            )

        assert count == 1
        session.commit.assert_awaited_once()
        mock_backfill.assert_awaited_once()
        mock_persist.assert_awaited_once()
        assert mock_persist.await_args.kwargs["matrix_version"] == 5
        assert mock_persist.await_args.kwargs["source"] == "td_expansion_snapshot"
