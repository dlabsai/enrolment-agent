import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypedDict

import logfire
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic_ai import Embedder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.models import (
    BaseRagModel,
    CatalogCourse,
    CatalogProgram,
    WordPressPage,
    # WordPressPost,
    WordPressProgram,
    load_catalog_courses,
    load_catalog_programs,
    load_wordpress_pages,
    # load_wordpress_posts,
    load_wordpress_programs,
)
from app.chat.tools.utils import get_azure_embedding_embedder
from app.core.db import get_session
from app.models import Document, DocumentContentChunk
from app.rag.wordpress.config import MIRROR_URL, WEBSITE_URL
from app.utils import configure_logfire

# CHUNK_SIZE = 256
# CHUNK_OVERLAP = 32
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
EMBEDDING_BATCH_SIZE = 100
MAX_CONCURRENT_BATCHES = 5

configure_logfire()


def _replace_wordpress_domain(text: str) -> str:
    """Replace WordPress staging domain with production domain."""
    return text.replace(MIRROR_URL, WEBSITE_URL)


@dataclass
class DocumentCategories:
    """Categorization of documents based on comparison with existing database."""

    new: list[BaseRagModel]  # Documents that don't exist in DB
    changed: list[BaseRagModel]  # Documents that exist but have been updated
    unchanged: list[tuple[BaseRagModel, Document]]  # Documents that haven't changed (source, db)
    deleted: list[Document]  # Documents in DB but not in source


def _create_batches[T](items: list[T], batch_size: int) -> list[list[T]]:
    """Split items into batches of specified size."""
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


async def _create_embeddings_batch(
    sem: asyncio.Semaphore, embedder: Embedder, texts: list[str]
) -> list[list[float]]:
    """Create embeddings for a batch of texts in a single API call."""
    async with sem:
        with logfire.span(f"create embeddings batch (size: {len(texts)})") as span:
            is_ai = True
            span.set_attribute("app.is_ai", is_ai)
            result = await embedder.embed_documents(texts)
            return [list(embedding) for embedding in result.embeddings]


def _get_document_type(model: BaseRagModel) -> str:
    if isinstance(model, WordPressPage):
        return "wp_page"
    # if isinstance(model, WordPressPost):
    #     return "wp_post"
    if isinstance(model, WordPressProgram):
        return "wp_program"
    if isinstance(model, CatalogProgram):
        return "catalog_program"
    if isinstance(model, CatalogCourse):
        return "catalog_course"
    raise ValueError(f"Unknown model type: {type(model)}")


class DocumentData(TypedDict):
    type: str
    id_: int
    title: str
    url: str
    markdown_content: str
    title_text: str
    title_embedding: list[float] | None
    source_created_at: datetime | None
    source_updated_at: datetime | None


type ChunkData = tuple[int, str]
type ChunkDataWithEmbedding = tuple[int, str, list[float]]
type DocumentDataWithChunks = tuple[DocumentData, list[ChunkData]]
type DocumentDataWithChunksAndEmbeddings = tuple[DocumentData, list[ChunkDataWithEmbedding]]


def _normalize_datetime(dt: datetime | None) -> datetime | None:
    """Normalize datetime to UTC timezone-aware, or None.

    Handles comparison between naive and timezone-aware datetimes by
    treating naive datetimes as UTC. This ensures consistent comparisons
    between source documents (which may have naive timestamps) and database
    records (which are always timezone-aware).

    Args:
        dt: A datetime that may be naive or timezone-aware, or None

    Returns:
        A timezone-aware datetime in UTC, or None if input was None

    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=UTC)
    return dt


async def _prepare_document_data[T: BaseRagModel](
    models: Sequence[T], text_splitter: RecursiveCharacterTextSplitter, model_type_name: str
) -> list[DocumentDataWithChunks]:
    """Prepare document data without creating SQLAlchemy models or embeddings.

    Returns a list of tuples (document_data, chunk_data_list).
    """
    document_data_list: list[DocumentDataWithChunks] = []

    for model in models:
        # Apply domain replacement for WordPress content
        is_wordpress = isinstance(model, (WordPressPage, WordPressProgram))
        title = _replace_wordpress_domain(model.title) if is_wordpress else model.title
        url = _replace_wordpress_domain(model.url) if is_wordpress else model.url
        markdown_content = (
            _replace_wordpress_domain(model.markdown_content)
            if is_wordpress
            else model.markdown_content
        )

        # Prepare document data
        # Normalize timestamps to ensure timezone-aware storage in UTC
        doc_data: DocumentData = {
            "type": _get_document_type(model),
            "id_": int(model.id),
            "title": title,
            "url": url,
            "markdown_content": markdown_content,
            "title_text": title,  # For embedding later
            "title_embedding": None,  # Will be filled later
            "source_created_at": _normalize_datetime(model.created),
            "source_updated_at": _normalize_datetime(model.updated),
        }

        # Split content into chunks
        text_chunks = text_splitter.split_text(markdown_content)

        # Prepare chunk data, filtering out chunks without alphanumeric characters
        chunk_data: list[ChunkData] = [
            (i, text_chunk)
            for i, text_chunk in enumerate(text_chunks)
            if any(char.isalnum() for char in text_chunk)
        ]

        document_data_list.append((doc_data, chunk_data))

    logfire.info(
        "Prepared {count} {type} documents with {chunk_count} total chunks",
        count=len(document_data_list),
        type=model_type_name,
        chunk_count=sum(len(chunks) for _, chunks in document_data_list),
    )

    return document_data_list


async def _create_embeddings_for_documents(
    embedder: Embedder, document_data_list: list[DocumentDataWithChunks]
) -> list[DocumentDataWithChunksAndEmbeddings]:
    """Create embeddings using batching for improved performance."""
    # Create semaphore for batch-level concurrency
    sem = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

    # Step 1: Collect all texts that need embeddings
    title_texts: list[str] = []
    chunk_texts: list[str] = []
    title_indices: list[int] = []  # Track which document each title belongs to
    chunk_indices: list[
        tuple[int, int]
    ] = []  # Track which (doc_idx, chunk_idx) each chunk belongs to

    for doc_idx, (doc_data, chunk_data) in enumerate(document_data_list):
        # Collect title text
        title_texts.append(doc_data["title_text"])
        title_indices.append(doc_idx)

        # Collect chunk texts
        for chunk_idx, (_, content) in enumerate(chunk_data):
            chunk_texts.append(content)
            chunk_indices.append((doc_idx, chunk_idx))

    # Step 2: Create batches
    title_batches = _create_batches(title_texts, EMBEDDING_BATCH_SIZE)
    chunk_batches = _create_batches(chunk_texts, EMBEDDING_BATCH_SIZE)

    # Step 3: Process title batches concurrently
    logfire.info(
        "Creating embeddings for {count} titles in {batches} batches",
        count=len(title_texts),
        batches=len(title_batches),
    )

    title_batch_tasks = [_create_embeddings_batch(sem, embedder, batch) for batch in title_batches]
    title_batch_results = await asyncio.gather(*title_batch_tasks)

    # Step 4: Process chunk batches concurrently
    logfire.info(
        "Creating embeddings for {count} chunks in {batches} batches",
        count=len(chunk_texts),
        batches=len(chunk_batches),
    )

    chunk_batch_tasks = [_create_embeddings_batch(sem, embedder, batch) for batch in chunk_batches]
    chunk_batch_results = await asyncio.gather(*chunk_batch_tasks)

    # Step 5: Flatten and map results back to documents
    # Flatten title results
    title_embeddings: list[list[float]] = []
    for batch_result in title_batch_results:
        title_embeddings.extend(batch_result)

    # Flatten chunk results
    chunk_embeddings: list[list[float]] = []
    for batch_result in chunk_batch_results:
        chunk_embeddings.extend(batch_result)

    # Step 6: Map embeddings back to documents
    # Update document data with title embeddings
    for i, embedding in enumerate(title_embeddings):
        doc_idx = title_indices[i]
        document_data_list[doc_idx][0]["title_embedding"] = embedding

    # Create result with chunk embeddings
    result: list[DocumentDataWithChunksAndEmbeddings] = []
    chunk_embedding_idx = 0

    for doc_data, chunk_data in document_data_list:
        doc_chunks_with_embeddings: list[ChunkDataWithEmbedding] = []

        for seq_num, content in chunk_data:
            embedding = chunk_embeddings[chunk_embedding_idx]
            doc_chunks_with_embeddings.append((seq_num, content, embedding))
            chunk_embedding_idx += 1

        result.append((doc_data, doc_chunks_with_embeddings))

    return result


async def _insert_documents_to_db(
    session: AsyncSession,
    document_data_list: list[DocumentDataWithChunksAndEmbeddings],
    model_type_name: str,
) -> None:
    """Insert all documents and chunks into the database."""
    document_count = 0
    chunk_count = 0

    # Insert all documents and chunks
    for doc_data, chunk_data in document_data_list:
        # Create and add document
        document = Document(
            type=doc_data["type"],
            id_=doc_data["id_"],
            title=doc_data["title"],
            url=doc_data["url"],
            markdown_content=doc_data["markdown_content"],
            title_embedding=doc_data["title_embedding"],
            source_created_at=doc_data["source_created_at"],
            source_updated_at=doc_data["source_updated_at"],
        )
        session.add(document)
        await session.flush()  # Flush to get the document ID

        # Create and add chunks
        for seq_num, content, embedding in chunk_data:
            chunk = DocumentContentChunk(
                sequence_number=seq_num,
                content=content,
                content_embedding=embedding,
                document_id=document.id,
            )
            session.add(chunk)

        document_count += 1
        chunk_count += len(chunk_data)

    logfire.info(
        "Inserted {count} {type} documents with {chunk_count} chunks into database",
        count=document_count,
        type=model_type_name,
        chunk_count=chunk_count,
    )


async def _process_documents[T: BaseRagModel](
    embedder: Embedder,
    session: AsyncSession,
    models: Sequence[T],
    text_splitter: RecursiveCharacterTextSplitter,
    model_type_name: str,
) -> None:
    """Process a list of documents with batched embedding creation."""
    # Step 1: Prepare document data without creating SQLAlchemy models
    document_data_list = await _prepare_document_data(models, text_splitter, model_type_name)

    # Step 2: Create embeddings using batching for improved performance
    document_data_with_embeddings = await _create_embeddings_for_documents(
        embedder, document_data_list
    )

    # Step 3: Insert all documents and chunks into the database
    await _insert_documents_to_db(session, document_data_with_embeddings, model_type_name)


async def _load_existing_documents(session: AsyncSession, doc_type: str) -> dict[int, Document]:
    """Load all existing documents of a given type from the database.

    Returns a dictionary keyed by document id_ for quick lookup.
    """
    result = await session.execute(select(Document).where(Document.type == doc_type))
    documents = result.scalars().all()
    return {doc.id_: doc for doc in documents}


def _categorize_documents(
    source_docs: Sequence[BaseRagModel], db_docs: dict[int, Document]
) -> DocumentCategories:
    """Categorize documents by comparing source data with existing database.

    Documents are categorized as:
    - NEW: Present in source but not in database
    - CHANGED: Present in both, but source_updated_at timestamp differs
    - UNCHANGED: Present in both with matching source_updated_at timestamp
    - DELETED: Present in database but not in source
    """
    new_docs: list[BaseRagModel] = []
    changed_docs: list[BaseRagModel] = []
    unchanged_docs: list[tuple[BaseRagModel, Document]] = []

    # Build source document map for quick lookup
    source_map = {int(doc.id): doc for doc in source_docs}

    # Categorize source documents
    for source_doc in source_docs:
        doc_id = int(source_doc.id)
        if doc_id not in db_docs:
            # Document doesn't exist in DB
            new_docs.append(source_doc)
        else:
            db_doc = db_docs[doc_id]
            # Normalize both timestamps to ensure consistent comparison
            # (handles timezone-aware vs naive datetime comparison)
            source_updated = _normalize_datetime(source_doc.updated)
            db_updated = _normalize_datetime(db_doc.source_updated_at)

            if source_updated != db_updated:
                # Document has been updated
                changed_docs.append(source_doc)
            else:
                # Document unchanged
                unchanged_docs.append((source_doc, db_doc))

    # Find deleted documents (in DB but not in source)
    deleted_docs = [db_doc for doc_id, db_doc in db_docs.items() if doc_id not in source_map]

    return DocumentCategories(
        new=new_docs, changed=changed_docs, unchanged=unchanged_docs, deleted=deleted_docs
    )


async def _process_new_documents(
    embedder: Embedder,
    session: AsyncSession,
    new_docs: list[BaseRagModel],
    text_splitter: RecursiveCharacterTextSplitter,
    model_type_name: str,
) -> None:
    """Process and insert new documents into the database."""
    if not new_docs:
        return

    with logfire.span(f"processing {len(new_docs)} new {model_type_name}"):
        await _process_documents(embedder, session, new_docs, text_splitter, model_type_name)


async def _process_changed_documents(
    embedder: Embedder,
    session: AsyncSession,
    changed_docs: list[BaseRagModel],
    text_splitter: RecursiveCharacterTextSplitter,
    model_type_name: str,
) -> None:
    """Process changed documents by updating existing records."""
    if not changed_docs:
        return

    with logfire.span(f"processing {len(changed_docs)} changed {model_type_name}"):
        # Prepare document data with chunks
        document_data_list = await _prepare_document_data(
            changed_docs, text_splitter, model_type_name
        )

        # Create embeddings
        document_data_with_embeddings = await _create_embeddings_for_documents(
            embedder, document_data_list
        )

        # Update documents in database
        for doc_data, chunk_data in document_data_with_embeddings:
            # Find existing document
            result = await session.execute(
                select(Document).where(
                    Document.type == doc_data["type"], Document.id_ == doc_data["id_"]
                )
            )
            existing_doc = result.scalar_one_or_none()

            if existing_doc:
                # Delete old chunks (cascade will handle this, but being explicit)
                await session.execute(
                    delete(DocumentContentChunk).where(
                        DocumentContentChunk.document_id == existing_doc.id
                    )
                )

                # Update document fields
                existing_doc.title = doc_data["title"]
                existing_doc.url = doc_data["url"]
                existing_doc.markdown_content = doc_data["markdown_content"]
                existing_doc.title_embedding = doc_data["title_embedding"]  # type: ignore[assignment]
                existing_doc.source_created_at = doc_data["source_created_at"]  # type: ignore[assignment]
                existing_doc.source_updated_at = doc_data["source_updated_at"]  # type: ignore[assignment]

                await session.flush()

                # Insert new chunks
                for seq_num, content, embedding in chunk_data:
                    chunk = DocumentContentChunk(
                        sequence_number=seq_num,
                        content=content,
                        content_embedding=embedding,
                        document_id=existing_doc.id,
                    )
                    session.add(chunk)

        logfire.info(
            "Updated {count} {type} documents", count=len(changed_docs), type=model_type_name
        )


async def _process_deleted_documents(
    session: AsyncSession, deleted_docs: list[Document], model_type_name: str
) -> None:
    """Delete documents that no longer exist in source data."""
    if not deleted_docs:
        return

    with logfire.span(f"deleting {len(deleted_docs)} {model_type_name}"):
        for doc in deleted_docs:
            await session.delete(doc)

        logfire.info(
            "Deleted {count} {type} documents", count=len(deleted_docs), type=model_type_name
        )


def _log_dry_run_stats(categories: DocumentCategories, model_type_name: str) -> None:
    """Log statistics for dry-run mode."""
    logfire.info(
        "[DRY RUN] {type}: {new} new, {changed} changed, {deleted} deleted, {unchanged} unchanged",
        type=model_type_name,
        new=len(categories.new),
        changed=len(categories.changed),
        deleted=len(categories.deleted),
        unchanged=len(categories.unchanged),
    )


def _log_update_stats(categories: DocumentCategories, model_type_name: str) -> None:
    """Log statistics for actual update."""
    logfire.info(
        "{type}: {new} new, {changed} changed, {deleted} deleted, {unchanged} unchanged",
        type=model_type_name,
        new=len(categories.new),
        changed=len(categories.changed),
        deleted=len(categories.deleted),
        unchanged=len(categories.unchanged),
    )


async def build_search_db(
    embedder: Embedder, *, force_rebuild: bool = False, dry_run: bool = False
) -> None:
    """Build or update the search database.

    This function supports two modes:

    1. **Incremental Update (default)**: Compares source documents with the database
       and only processes new, changed, or deleted documents. This is significantly
       faster and more cost-effective for large datasets where most documents are
       unchanged between runs.

       The incremental update works in three phases:
       - Phase 1 (Discovery): Load source documents and existing DB documents,
         then categorize each document as NEW, CHANGED, UNCHANGED, or DELETED
         by comparing source_updated_at timestamps.
       - Phase 2 (Update): Process only the documents that need updates:
         * NEW: Create embeddings and insert into database
         * CHANGED: Delete old chunks, update document, create new embeddings
         * DELETED: Remove from database
         * UNCHANGED: Skip entirely (no processing)
       - Phase 3 (Commit): Save all changes in a single atomic transaction

       Performance: For a typical update with 1000 total documents where 50 are new,
       20 changed, and 10 deleted, this provides ~12.5x speedup by only processing
       80 documents instead of 1000.

    2. **Full Rebuild (--force-rebuild)**: Deletes all documents and recreates
       from scratch. Use this when:
       - Database schema has changed
       - Embedding model has changed
       - You want to ensure a clean slate
       - There are data inconsistencies

    Args:
        embedder: Embedder used to create embeddings.
        force_rebuild: If True, delete all documents and rebuild from scratch
        dry_run: If True, only preview changes without committing to database.
                 Useful for checking what would be updated before running the actual update.

    Examples:
        # Incremental update (default, recommended)
        python -m app.rag.build

        # Preview changes without committing
        python -m app.rag.build --dry-run

        # Force full rebuild
        python -m app.rag.build --force-rebuild

        # Preview full rebuild
        python -m app.rag.build --force-rebuild --dry-run

    """
    mode_desc = "DRY RUN - " if dry_run else ""
    rebuild_desc = "full rebuild" if force_rebuild else "incremental update"
    with logfire.span(f"{mode_desc}build embedding database ({rebuild_desc})"):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, length_function=len
        )

        async with get_session() as session:
            if force_rebuild:
                # Full rebuild: delete all and recreate
                logfire.info("Performing full rebuild - deleting all documents")
                if not dry_run:
                    await session.execute(delete(Document))

                # Process all document types
                for loader, name in [
                    (load_catalog_programs, "Catalog programs"),
                    (load_catalog_courses, "Catalog courses"),
                    (load_wordpress_pages, "WordPress pages"),
                    # (load_wordpress_posts, "WordPress posts"),
                    (load_wordpress_programs, "WordPress programs"),
                ]:
                    with logfire.span(f"processing {name}"):
                        source_docs = list(loader())
                        if dry_run:
                            logfire.info(
                                "[DRY RUN] Would process {count} {type} documents",
                                count=len(source_docs),
                                type=name,
                            )
                        else:
                            await _process_documents(
                                embedder, session, source_docs, text_splitter, name
                            )
            else:
                # Incremental update: compare and update only changed documents
                logfire.info("Performing incremental update")

                for loader, name, doc_type in [
                    (load_catalog_programs, "Catalog programs", "catalog_program"),
                    (load_catalog_courses, "Catalog courses", "catalog_course"),
                    (load_wordpress_pages, "WordPress pages", "wp_page"),
                    # (load_wordpress_posts, "WordPress posts", "wp_post"),
                    (load_wordpress_programs, "WordPress programs", "wp_program"),
                ]:
                    with logfire.span(f"processing {name}"):
                        # Phase 1: Discovery - load and categorize documents
                        source_docs = list(loader())
                        db_docs = await _load_existing_documents(session, doc_type)
                        categories = _categorize_documents(source_docs, db_docs)

                        if dry_run:
                            # Just log what would happen
                            _log_dry_run_stats(categories, name)
                        else:
                            # Phase 2: Update - process each category
                            await _process_new_documents(
                                embedder, session, categories.new, text_splitter, name
                            )
                            await _process_changed_documents(
                                embedder, session, categories.changed, text_splitter, name
                            )
                            await _process_deleted_documents(session, categories.deleted, name)

                            # Log stats
                            _log_update_stats(categories, name)

            # Phase 3: Commit - save all changes atomically
            if not dry_run:
                await session.commit()
                logfire.info("Database changes committed successfully")
            else:
                logfire.info("DRY RUN complete - no changes committed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or update the search database with document embeddings"
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force a full rebuild by deleting all documents and recreating from scratch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing to database (shows what would be "
        "added/changed/deleted)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        build_search_db(
            get_azure_embedding_embedder(), force_rebuild=args.force_rebuild, dry_run=args.dry_run
        )
    )
