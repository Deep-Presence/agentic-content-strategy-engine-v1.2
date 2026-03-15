#!/usr/bin/env python3
"""One-time migration: ChromaDB → pgvector.

Reads all existing ChromaDB collections from artifacts/chroma_db/ and bulk
inserts them into pgvector tables (semantic_units, paragraph_embeddings,
persona_embeddings).

Usage:
  python scripts/migrate_chroma_to_pgvector.py [--chroma-dir artifacts/chroma_db] [--dry-run]

Safety:
  - Idempotent (ON CONFLICT DO NOTHING on unique constraints).
  - Does NOT delete ChromaDB data — manual cleanup after verification.
  - Temporarily imports chromadb for reading; can be uninstalled after.

Requirements:
  - DATABASE_URL env var must be set.
  - chromadb package must still be installed (pip install chromadb).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Migrate ChromaDB data to pgvector.")
    p.add_argument(
        "--chroma-dir",
        default=str(_PROJECT_ROOT / "artifacts" / "chroma_db"),
        help="Path to ChromaDB persistence directory.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be migrated without writing to pgvector.",
    )
    return p.parse_args()


def _extract_slug(collection_name: str, prefix: str) -> str | None:
    """Extract company slug from collection name like 'gap_company_ramp'."""
    if collection_name.startswith(prefix):
        return collection_name[len(prefix):]
    return None


async def _migrate_company_collections(
    chroma_client,
    dry_run: bool,
) -> dict[str, int]:
    """Migrate gap_company_* collections → semantic_units table."""
    from core.shared_tools.vector_store import async_upsert_embeddings

    stats: dict[str, int] = {}
    collections = chroma_client.list_collections()

    for col_meta in collections:
        name = col_meta.name if hasattr(col_meta, "name") else str(col_meta)
        slug = _extract_slug(name, "gap_company_")
        if not slug:
            continue

        col = chroma_client.get_collection(name)
        data = col.get(include=["embeddings", "documents", "metadatas"])

        ids = data.get("ids", [])
        embeddings = data.get("embeddings", [])
        documents = data.get("documents", [])

        if not ids:
            logger.info("  %s: empty, skipping.", name)
            continue

        logger.info("  %s: %d items", name, len(ids))
        stats[name] = len(ids)

        if dry_run:
            continue

        texts = documents if documents else [""] * len(ids)
        await async_upsert_embeddings(
            company_slug=slug,
            unit_ids=ids,
            texts=texts,
            embeddings=embeddings,
        )

    return stats


async def _migrate_citation_collections(
    chroma_client,
    dry_run: bool,
) -> dict[str, int]:
    """Migrate gap_citations_* collections → paragraph_embeddings table."""
    from core.shared_tools.vector_store import async_upsert_citation_embeddings

    stats: dict[str, int] = {}
    collections = chroma_client.list_collections()

    for col_meta in collections:
        name = col_meta.name if hasattr(col_meta, "name") else str(col_meta)
        slug = _extract_slug(name, "gap_citations_")
        if not slug:
            continue

        col = chroma_client.get_collection(name)
        data = col.get(include=["embeddings", "documents"])

        ids = data.get("ids", [])
        embeddings = data.get("embeddings", [])
        documents = data.get("documents", [])

        if not ids:
            logger.info("  %s: empty, skipping.", name)
            continue

        logger.info("  %s: %d items", name, len(ids))
        stats[name] = len(ids)

        if dry_run:
            continue

        docs = documents if documents else [""] * len(ids)
        await async_upsert_citation_embeddings(
            company_slug=slug,
            embedding_ids=ids,
            documents=docs,
            embeddings=embeddings,
        )

    return stats


async def _migrate_persona_collections(
    chroma_client,
    dry_run: bool,
) -> dict[str, int]:
    """Migrate persona_* collections → persona_embeddings table."""
    from core.shared_tools.vector_store import async_upsert_persona_embeddings

    stats: dict[str, int] = {}
    collections = chroma_client.list_collections()

    for col_meta in collections:
        name = col_meta.name if hasattr(col_meta, "name") else str(col_meta)
        slug = _extract_slug(name, "persona_")
        if not slug:
            continue

        col = chroma_client.get_collection(name)
        data = col.get(include=["embeddings", "documents"])

        ids = data.get("ids", [])
        embeddings = data.get("embeddings", [])
        documents = data.get("documents", [])

        if not ids:
            logger.info("  %s: empty, skipping.", name)
            continue

        logger.info("  %s: %d items", name, len(ids))
        stats[name] = len(ids)

        if dry_run:
            continue

        texts = documents if documents else [""] * len(ids)
        await async_upsert_persona_embeddings(
            effective_slug=slug,
            persona_ids=ids,
            texts=texts,
            embeddings=embeddings,
        )

    return stats


async def main() -> int:
    args = _parse_args()
    chroma_dir = Path(args.chroma_dir)

    if not chroma_dir.exists():
        logger.error("ChromaDB directory not found: %s", chroma_dir)
        logger.info("Nothing to migrate. If ChromaDB data was already removed, this is expected.")
        return 0

    try:
        import chromadb
    except ImportError:
        logger.error(
            "chromadb package not installed. Install temporarily: pip install chromadb\n"
            "After migration, uninstall: pip uninstall chromadb"
        )
        return 1

    if not args.dry_run:
        import os
        if not os.environ.get("DATABASE_URL"):
            logger.error("DATABASE_URL not set. Required for pgvector writes.")
            return 1

    logger.info("=" * 60)
    logger.info("ChromaDB → pgvector Migration")
    logger.info("Source: %s", chroma_dir)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("=" * 60)

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collections = client.list_collections()
    col_names = [c.name if hasattr(c, "name") else str(c) for c in collections]
    logger.info("Found %d collections: %s", len(col_names), col_names)

    # Migrate company asset embeddings
    logger.info("\n--- Company Asset Embeddings ---")
    company_stats = await _migrate_company_collections(client, args.dry_run)

    # Migrate citation embeddings
    logger.info("\n--- Citation Embeddings ---")
    citation_stats = await _migrate_citation_collections(client, args.dry_run)

    # Migrate persona embeddings
    logger.info("\n--- Persona Embeddings ---")
    persona_stats = await _migrate_persona_collections(client, args.dry_run)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Migration Summary%s", " (DRY RUN)" if args.dry_run else "")
    logger.info("=" * 60)

    total = 0
    for label, stats in [
        ("Company", company_stats),
        ("Citation", citation_stats),
        ("Persona", persona_stats),
    ]:
        count = sum(stats.values())
        total += count
        logger.info("  %s: %d items across %d collections", label, count, len(stats))

    logger.info("  Total: %d items migrated", total)

    if not args.dry_run and total > 0:
        logger.info(
            "\nMigration complete. Verify data in pgvector tables, then:\n"
            "  1. Remove ChromaDB data: rm -rf %s\n"
            "  2. Uninstall: pip uninstall chromadb",
            chroma_dir,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
