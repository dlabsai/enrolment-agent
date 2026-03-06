"""RAG data fixtures for integration tests.

This module provides functionality to populate and manage RAG data (Document and
DocumentContentChunk tables) for integration tests. The RAG data is expensive to
create (requires embedding API calls) so it's designed to be:

1. Created once and persisted in the database
2. Reused across multiple test sessions
3. Only recreated when explicitly requested via --rebuild-rag flag

Usage:
    # First time or when RAG data needs refresh:
    pytest -m integration --rebuild-rag

    # Normal test runs (uses existing RAG data):
    pytest -m integration
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Document, DocumentContentChunk


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory with consistent settings."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def _get_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Create a session from an engine."""
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session


async def check_rag_data_exists(engine: AsyncEngine) -> bool:
    """Check if RAG data already exists in the database.

    Returns True if there are documents in the database, False otherwise.
    """
    async with _get_session(engine) as session:
        result = await session.execute(select(func.count(Document.id)))
        count = result.scalar()
        return count is not None and count > 0


async def get_rag_data_stats(engine: AsyncEngine) -> dict[str, int]:
    """Get statistics about RAG data in the database."""
    async with _get_session(engine) as session:
        doc_result = await session.execute(select(func.count(Document.id)))
        doc_count = doc_result.scalar() or 0

        chunk_result = await session.execute(select(func.count(DocumentContentChunk.id)))
        chunk_count = chunk_result.scalar() or 0

        # Get counts by document type
        type_result = await session.execute(
            select(Document.type, func.count(Document.id)).group_by(Document.type)
        )
        type_counts = {row[0]: row[1] for row in type_result.fetchall()}

        return {
            "total_documents": doc_count,
            "total_chunks": chunk_count,
            **{f"doc_type_{k}": v for k, v in type_counts.items()},
        }


async def populate_rag_data(engine: AsyncEngine) -> None:
    """Populate RAG data using the build.py core functions.

    This imports and calls the build functions to create embeddings
    and populate the Document and DocumentContentChunk tables.
    """
    from app.chat.tools.utils import get_azure_embedding_embedder
    from app.rag.build import build_search_db

    # Run the build with force_rebuild to ensure clean state
    await build_search_db(get_azure_embedding_embedder(), force_rebuild=True, dry_run=False)


async def clear_non_rag_tables(session: AsyncSession) -> None:
    """Clear all tables except Document and DocumentContentChunk.

    This is used between tests to ensure clean state for conversation data
    while preserving the expensive RAG data.
    """
    # Tables to clear (in order to respect foreign key constraints)
    tables_to_clear = [
        "otel_span",
        "message_feedback",
        "conversation_feedback",
        "message",
        "conversation",
        # Note: We keep 'user' table as test_user fixture manages it
        # Note: We keep 'document' and 'document_content_chunk' (RAG data)
    ]

    for table in tables_to_clear:
        await session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

    await session.commit()


def run_rag_population_sync(engine: AsyncEngine) -> None:
    """Wrap populate_rag_data for synchronous execution."""
    asyncio.run(populate_rag_data(engine))
