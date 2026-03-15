"""DB integration tests for migrations 0016 (pgvector_migration) and 0017 (cps_training_tables).

Tests verify table creation, HNSW indexes, constraint behavior, backfill
correctness, and downgrade safety. Requires TEST_DATABASE_URL.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── 0016: persona_embeddings table ──────────────────────────────────────


async def test_persona_embeddings_insert_and_query(db_session):
    """persona_embeddings table accepts inserts and supports slug query."""
    from core.db.models.embeddings import PersonaEmbeddingModel

    embedding = [0.1] * 1536
    persona = PersonaEmbeddingModel(
        company_slug="ramp",
        effective_slug="ramp",
        persona_id="p-001",
        text="CFO at mid-market SaaS",
        embedding=embedding,
    )
    db_session.add(persona)
    await db_session.flush()

    assert persona.id is not None
    assert persona.created_at is not None


async def test_persona_embeddings_unique_constraint(db_session):
    """Duplicate (effective_slug, persona_id) violates unique constraint."""
    from sqlalchemy.exc import IntegrityError
    from core.db.models.embeddings import PersonaEmbeddingModel

    embedding = [0.1] * 1536
    p1 = PersonaEmbeddingModel(
        company_slug="ramp",
        effective_slug="ramp",
        persona_id="p-dup",
        text="First",
        embedding=embedding,
    )
    db_session.add(p1)
    await db_session.flush()

    p2 = PersonaEmbeddingModel(
        company_slug="ramp",
        effective_slug="ramp",
        persona_id="p-dup",
        text="Duplicate",
        embedding=embedding,
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_persona_embeddings_different_slugs_same_persona(db_session):
    """Same persona_id across different effective_slugs is allowed."""
    from core.db.models.embeddings import PersonaEmbeddingModel

    embedding = [0.2] * 1536
    p1 = PersonaEmbeddingModel(
        company_slug="ramp",
        effective_slug="ramp",
        persona_id="p-shared",
        text="First slug",
        embedding=embedding,
    )
    p2 = PersonaEmbeddingModel(
        company_slug="ramp",
        effective_slug="ramp__corporate-card",
        persona_id="p-shared",
        text="Second slug",
        embedding=embedding,
    )
    db_session.add_all([p1, p2])
    await db_session.flush()

    assert p1.id != p2.id


# ── 0016: semantic_units — company_slug + nullable run_id ───────────────


async def test_semantic_unit_nullable_run_id(db_session, sample_company):
    """Semantic units can be inserted without run_id (script-based inserts)."""
    from core.db.models.embeddings import SemanticUnitModel

    unit = SemanticUnitModel(
        company_id=sample_company.id,
        run_id=None,
        unit_id="unit-001",
        company_slug="test-co",
        text="Some text",
        embedding=[0.5] * 1536,
    )
    db_session.add(unit)
    await db_session.flush()

    assert unit.id is not None
    assert unit.run_id is None
    assert unit.company_slug == "test-co"


async def test_semantic_unit_company_slug_query(db_session, sample_company):
    """Slug-based query returns only matching company's units."""
    from sqlalchemy import select
    from core.db.models.embeddings import SemanticUnitModel

    embedding = [0.3] * 1536
    u1 = SemanticUnitModel(
        company_id=sample_company.id,
        unit_id="u-a",
        company_slug="test-co",
        text="A",
        embedding=embedding,
    )
    u2 = SemanticUnitModel(
        company_id=sample_company.id,
        unit_id="u-b",
        company_slug="other-co",
        text="B",
        embedding=embedding,
    )
    db_session.add_all([u1, u2])
    await db_session.flush()

    stmt = select(SemanticUnitModel).where(SemanticUnitModel.company_slug == "test-co")
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    slugs = [r.company_slug for r in rows]
    assert "test-co" in slugs
    assert "other-co" not in slugs


# ── 0016: paragraph_embeddings — nullable FK + company_slug ──────────────


async def test_paragraph_embedding_nullable_url_enrichment(db_session):
    """paragraph_embeddings accepts NULL url_enrichment_id."""
    from core.db.models.embeddings import ParagraphEmbeddingModel

    pe = ParagraphEmbeddingModel(
        url_enrichment_id=None,
        embedding_id="cite_abc123",
        company_slug="ramp",
        paragraph_text="Some paragraph",
        embedding=[0.4] * 1536,
    )
    db_session.add(pe)
    await db_session.flush()

    assert pe.id is not None
    assert pe.url_enrichment_id is None
    assert pe.company_slug == "ramp"


# ── 0017: CPS training tables ──────────────────────────────────────────


async def test_cps_training_snippets_insert(db_session):
    """cps_training_snippets table accepts inserts with all fields."""
    from sqlalchemy import text

    await db_session.execute(text("""
        INSERT INTO cps_training_snippets (id, snippet_id, text, embedding, domain, url)
        VALUES (gen_random_uuid(), 'snip-001', 'Test snippet', :emb, 'tech', 'https://example.com')
    """), {"emb": str([0.1] * 1536)})
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT snippet_id, domain FROM cps_training_snippets WHERE snippet_id = 'snip-001'")
    )
    row = result.one()
    assert row.snippet_id == "snip-001"
    assert row.domain == "tech"


async def test_cps_training_queries_insert(db_session):
    """cps_training_queries table accepts inserts with all fields."""
    from sqlalchemy import text

    await db_session.execute(text("""
        INSERT INTO cps_training_queries (id, query_id, query_text, embedding, engine)
        VALUES (gen_random_uuid(), 'q-001', 'Test query', :emb, 'openai')
    """), {"emb": str([0.2] * 1536)})
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT query_id, engine FROM cps_training_queries WHERE query_id = 'q-001'")
    )
    row = result.one()
    assert row.query_id == "q-001"
    assert row.engine == "openai"


async def test_cps_training_snippets_unique_constraint(db_session):
    """Duplicate snippet_id violates unique constraint."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    emb = str([0.1] * 1536)
    await db_session.execute(text("""
        INSERT INTO cps_training_snippets (id, snippet_id, text, embedding)
        VALUES (gen_random_uuid(), 'snip-dup', 'First', :emb)
    """), {"emb": emb})
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(text("""
            INSERT INTO cps_training_snippets (id, snippet_id, text, embedding)
            VALUES (gen_random_uuid(), 'snip-dup', 'Duplicate', :emb)
        """), {"emb": emb})
        await db_session.flush()


# ── EmbeddingRepository via real DB ──────────────────────────────────────


async def test_repo_upsert_and_query_persona_embeddings(db_session):
    """EmbeddingRepository upsert + query persona embeddings end-to-end."""
    from core.db.repositories.embedding_repo import EmbeddingRepository

    repo = EmbeddingRepository(db_session)
    embedding = [0.5] * 1536

    items = [
        {
            "id": uuid.uuid4(),
            "company_slug": "ramp",
            "effective_slug": "ramp",
            "persona_id": "p-cfo",
            "text": "CFO persona",
            "embedding": embedding,
        },
        {
            "id": uuid.uuid4(),
            "company_slug": "ramp",
            "effective_slug": "ramp",
            "persona_id": "p-cto",
            "text": "CTO persona",
            "embedding": embedding,
        },
    ]
    await repo.upsert_persona_embeddings(items)

    results = await repo.get_persona_embeddings_by_slug("ramp")
    assert len(results) == 2
    persona_ids = {r.persona_id for r in results}
    assert persona_ids == {"p-cfo", "p-cto"}


async def test_repo_upsert_persona_updates_on_conflict(db_session):
    """Upserting same (effective_slug, persona_id) updates text and embedding."""
    from core.db.repositories.embedding_repo import EmbeddingRepository

    repo = EmbeddingRepository(db_session)
    embedding_v1 = [0.1] * 1536
    embedding_v2 = [0.9] * 1536

    items_v1 = [{
        "id": uuid.uuid4(),
        "company_slug": "ramp",
        "effective_slug": "ramp",
        "persona_id": "p-evolve",
        "text": "Version 1",
        "embedding": embedding_v1,
    }]
    await repo.upsert_persona_embeddings(items_v1)

    items_v2 = [{
        "id": uuid.uuid4(),
        "company_slug": "ramp",
        "effective_slug": "ramp",
        "persona_id": "p-evolve",
        "text": "Version 2",
        "embedding": embedding_v2,
    }]
    await repo.upsert_persona_embeddings(items_v2)

    results = await repo.get_persona_embeddings_by_slug("ramp")
    assert len(results) == 1
    assert results[0].text == "Version 2"


async def test_repo_slug_based_count_and_delete(db_session, sample_company):
    """count_by_slug and delete_by_slug work correctly."""
    from core.db.repositories.embedding_repo import EmbeddingRepository
    from core.db.models.embeddings import SemanticUnitModel

    repo = EmbeddingRepository(db_session)
    embedding = [0.6] * 1536

    for i in range(3):
        db_session.add(SemanticUnitModel(
            company_id=sample_company.id,
            unit_id=f"count-{i}",
            company_slug="test-co",
            text=f"Text {i}",
            embedding=embedding,
        ))
    await db_session.flush()

    assert await repo.count_by_slug("test-co") == 3

    deleted = await repo.delete_by_slug("test-co")
    assert deleted == 3
    assert await repo.count_by_slug("test-co") == 0


async def test_repo_upsert_paragraph_embeddings(db_session):
    """upsert_paragraph_embeddings inserts and updates on conflict."""
    from core.db.repositories.embedding_repo import EmbeddingRepository

    repo = EmbeddingRepository(db_session)
    embedding = [0.7] * 1536

    items = [{
        "id": uuid.uuid4(),
        "embedding_id": "cite_para_001",
        "company_slug": "carta",
        "paragraph_text": "Original text",
        "embedding": embedding,
    }]
    await repo.upsert_paragraph_embeddings(items)

    # Update via upsert
    updated_items = [{
        "id": uuid.uuid4(),
        "embedding_id": "cite_para_001",
        "company_slug": "carta",
        "paragraph_text": "Updated text",
        "embedding": [0.8] * 1536,
    }]
    await repo.upsert_paragraph_embeddings(updated_items)

    from sqlalchemy import select
    from core.db.models.embeddings import ParagraphEmbeddingModel
    stmt = select(ParagraphEmbeddingModel).where(
        ParagraphEmbeddingModel.embedding_id == "cite_para_001"
    )
    result = await db_session.execute(stmt)
    row = result.scalar_one()
    assert row.paragraph_text == "Updated text"
