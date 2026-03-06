"""Tests for ORM model creation, constraints, and relationships."""
from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from core.db.enums import (
    GapClassification,
    PipelineStatus,
    PipelineType,
    StageStatus,
    TrackingStatus,
    UserRole,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── CompanyModel ──────────────────────────────────────────────────────


async def test_company_create(db_session):
    """CompanyModel can be created with valid data and gets a UUID pk."""
    from core.db.models.organization import CompanyModel

    company = CompanyModel(slug="acme", name="Acme Inc", domain="acme.com")
    db_session.add(company)
    await db_session.flush()

    assert company.id is not None
    assert company.slug == "acme"
    assert company.name == "Acme Inc"
    assert company.domain == "acme.com"
    assert company.is_archived is False


async def test_company_slug_unique_constraint(db_session):
    """Inserting two companies with the same slug raises IntegrityError."""
    from core.db.models.organization import CompanyModel

    c1 = CompanyModel(slug="dup-co", name="First", domain="first.com")
    db_session.add(c1)
    await db_session.flush()

    c2 = CompanyModel(slug="dup-co", name="Second", domain="second.com")
    db_session.add(c2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_company_timestamps_auto_set(db_session):
    """created_at and updated_at are automatically populated after flush."""
    from core.db.models.organization import CompanyModel

    company = CompanyModel(slug="ts-co", name="Timestamp Co", domain="ts.com")
    db_session.add(company)
    await db_session.flush()

    assert company.created_at is not None
    assert company.updated_at is not None


# ── ProductModel ──────────────────────────────────────────────────────


async def test_product_unique_company_slug(db_session, sample_company):
    """ProductModel respects UNIQUE(company_id, slug) constraint."""
    from core.db.models.organization import ProductModel

    p1 = ProductModel(
        company_id=sample_company.id, slug="widget", name="Widget"
    )
    db_session.add(p1)
    await db_session.flush()

    p2 = ProductModel(
        company_id=sample_company.id, slug="widget", name="Widget 2"
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_product_same_slug_different_company(db_session, sample_company):
    """Same product slug under a different company is allowed."""
    from core.db.models.organization import CompanyModel, ProductModel

    other = CompanyModel(slug="other-co", name="Other", domain="other.com")
    db_session.add(other)
    await db_session.flush()

    p1 = ProductModel(
        company_id=sample_company.id, slug="shared-slug", name="P1"
    )
    p2 = ProductModel(
        company_id=other.id, slug="shared-slug", name="P2"
    )
    db_session.add_all([p1, p2])
    await db_session.flush()

    assert p1.id != p2.id


# ── UserModel ─────────────────────────────────────────────────────────


async def test_user_email_unique(db_session, sample_company):
    """Duplicate emails raise IntegrityError."""
    from core.db.models.organization import UserModel

    u1 = UserModel(
        company_id=sample_company.id,
        email="unique@test.com",
        password_hash="hash1",
        role=UserRole.member,
    )
    db_session.add(u1)
    await db_session.flush()

    u2 = UserModel(
        company_id=sample_company.id,
        email="unique@test.com",
        password_hash="hash2",
        role=UserRole.member,
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_user_timestamps_auto_set(db_session, sample_company):
    """UserModel gets created_at/updated_at from TimestampMixin."""
    from core.db.models.organization import UserModel

    user = UserModel(
        company_id=sample_company.id,
        email="ts-user@test.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.created_at is not None
    assert user.updated_at is not None


# ── PipelineRunModel ──────────────────────────────────────────────────


async def test_pipeline_run_self_referential_fk(db_session, sample_company):
    """PipelineRunModel parent_run_id self-referential FK works."""
    from core.db.models.pipelines import PipelineRunModel

    parent = PipelineRunModel(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.completed,
    )
    db_session.add(parent)
    await db_session.flush()

    child = PipelineRunModel(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.content,
        status=PipelineStatus.running,
        parent_run_id=parent.id,
    )
    db_session.add(child)
    await db_session.flush()

    assert child.parent_run_id == parent.id


async def test_pipeline_run_timestamps(db_session, sample_company):
    """PipelineRunModel timestamps are auto-populated."""
    from core.db.models.pipelines import PipelineRunModel

    run = PipelineRunModel(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.research,
        status=PipelineStatus.pending,
    )
    db_session.add(run)
    await db_session.flush()

    assert run.created_at is not None
    assert run.updated_at is not None


# ── PipelineStageLogModel cascade ─────────────────────────────────────


async def test_stage_log_cascade_delete(db_session, sample_company):
    """Deleting a pipeline run cascades to its stage logs."""
    from core.db.models.pipelines import PipelineRunModel, PipelineStageLogModel
    from sqlalchemy import select

    run = PipelineRunModel(
        company_id=sample_company.id,
        effective_slug="test-co",
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.running,
    )
    db_session.add(run)
    await db_session.flush()

    log = PipelineStageLogModel(
        run_id=run.id,
        stage_name="s1_embed_assets",
        status=StageStatus.completed,
    )
    db_session.add(log)
    await db_session.flush()
    log_id = log.id

    # Delete the run — should cascade
    await db_session.delete(run)
    await db_session.flush()

    result = await db_session.execute(
        select(PipelineStageLogModel).where(PipelineStageLogModel.id == log_id)
    )
    assert result.scalars().first() is None


# ── TrackingSnapshotModel partial unique ──────────────────────────────


async def test_tracking_snapshot_no_product_partial_unique(db_session, sample_company):
    """Duplicate company+date with NULL product_id should fail on partial unique index."""
    from core.db.models.tracking import TrackingSnapshotModel

    snap_date = date(2026, 1, 15)

    s1 = TrackingSnapshotModel(
        company_id=sample_company.id,
        product_id=None,
        snapshot_date=snap_date,
        status=TrackingStatus.pending,
    )
    db_session.add(s1)
    await db_session.flush()

    s2 = TrackingSnapshotModel(
        company_id=sample_company.id,
        product_id=None,
        snapshot_date=snap_date,
        status=TrackingStatus.pending,
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_tracking_snapshot_with_product_partial_unique(
    db_session, sample_company
):
    """Duplicate company+product+date should fail on partial unique index."""
    from core.db.models.organization import ProductModel
    from core.db.models.tracking import TrackingSnapshotModel

    product = ProductModel(
        company_id=sample_company.id, slug="prod-a", name="Product A"
    )
    db_session.add(product)
    await db_session.flush()

    snap_date = date(2026, 2, 20)

    s1 = TrackingSnapshotModel(
        company_id=sample_company.id,
        product_id=product.id,
        snapshot_date=snap_date,
        status=TrackingStatus.pending,
    )
    db_session.add(s1)
    await db_session.flush()

    s2 = TrackingSnapshotModel(
        company_id=sample_company.id,
        product_id=product.id,
        snapshot_date=snap_date,
        status=TrackingStatus.pending,
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
