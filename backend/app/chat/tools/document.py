from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import logfire
from pydantic_ai import Embedder, RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools.deps import Deps
from app.chat.tools.models import (
    Document,
    DocumentChunkResult,
    DocumentTitleResult,
    DocumentType,
    NotFoundIds,
    TruncatedDocInfo,
)
from app.llm.tokens import count_tokens, get_encoding
from app.models import Document as DBDocument
from app.models import DocumentContentChunk

_RETRIEVE_DOCUMENTS_MAX_TOKENS = 32_000
_RETRIEVE_DOCUMENTS_MAX_DOCUMENT_TOKENS = 16_000

_DOCUMENT_TYPES: set[DocumentType] = {"wp_page", "wp_program", "catalog_program", "catalog_course"}


def _coerce_document_type(value: str) -> DocumentType | None:
    if value in _DOCUMENT_TYPES:
        return value
    return None


def _truncate_to_token_limit(text: str, token_limit: int) -> tuple[str, int, int]:
    encoding = get_encoding()
    original_tokens = count_tokens(text)

    if original_tokens <= token_limit:
        return text, original_tokens, original_tokens

    truncated_content = encoding.decode(encoding.encode(text)[:token_limit])
    truncated_tokens = count_tokens(truncated_content)

    return truncated_content, original_tokens, truncated_tokens


async def _retrieve_documents_db(
    wp_page_ids: list[int] | None = None,
    wp_program_ids: list[int] | None = None,
    catalog_program_ids: list[int] | None = None,
    catalog_course_ids: list[int] | None = None,
    *,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> tuple[list[Document], NotFoundIds | None, TruncatedDocInfo | None]:
    logfire.info(
        "retrieve documents: {wp_page_ids=} {wp_program_ids=}",
        wp_page_ids=wp_page_ids,
        wp_program_ids=wp_program_ids,
        catalog_program_ids=catalog_program_ids,
        catalog_course_ids=catalog_course_ids,
    )

    documents: list[Document] = []
    not_found_ids = NotFoundIds()
    truncated_info = TruncatedDocInfo()
    total_tokens = 0
    all_documents: list[Document] = []

    query_criteria: list[tuple[str, list[int]]] = []
    if wp_page_ids:
        query_criteria.append(("wp_page", wp_page_ids))
    if wp_program_ids:
        query_criteria.append(("wp_program", wp_program_ids))
    if catalog_program_ids:
        query_criteria.append(("catalog_program", catalog_program_ids))
    if catalog_course_ids:
        query_criteria.append(("catalog_course", catalog_course_ids))

    async with session_factory() as session:
        for doc_type, doc_ids in query_criteria:
            stmt = select(DBDocument).where(
                DBDocument.type == doc_type, DBDocument.id_.in_(doc_ids)
            )
            result = await session.execute(stmt)
            db_docs = result.scalars().all()

            found_ids = {doc.id_ for doc in db_docs}
            not_found = [doc_id for doc_id in doc_ids if doc_id not in found_ids]

            if not_found:
                if doc_type == "wp_page":
                    not_found_ids.not_found_wp_page = not_found
                elif doc_type == "wp_program":
                    not_found_ids.not_found_wp_program = not_found
                elif doc_type == "catalog_program":
                    not_found_ids.not_found_catalog_program = not_found
                elif doc_type == "catalog_course":
                    not_found_ids.not_found_catalog_course = not_found

            for db_doc in db_docs:
                coerced_type = _coerce_document_type(db_doc.type)
                if coerced_type is None:
                    continue
                all_documents.append(
                    Document(
                        type=coerced_type,
                        id=db_doc.id_,
                        title=db_doc.title,
                        url=db_doc.url,
                        content=db_doc.markdown_content,
                        updated_at=db_doc.source_updated_at,
                    )
                )

    has_not_found_ids = (
        bool(not_found_ids.not_found_wp_page)
        or bool(not_found_ids.not_found_wp_program)
        or bool(not_found_ids.not_found_catalog_program)
        or bool(not_found_ids.not_found_catalog_course)
    )

    has_truncation = False

    for doc in all_documents:
        doc_tokens = count_tokens(doc.content)
        doc_to_add = doc
        was_truncated = False

        if doc_tokens > _RETRIEVE_DOCUMENTS_MAX_DOCUMENT_TOKENS:
            truncated_content, original_tokens, truncated_tokens = _truncate_to_token_limit(
                doc.content, _RETRIEVE_DOCUMENTS_MAX_DOCUMENT_TOKENS
            )
            percentage_preserved = round((truncated_tokens / original_tokens) * 100, 1)

            truncated_content += (
                "\n\n[Content truncated due to document size limit. "
                f"{percentage_preserved}% of original content preserved.]"
            )

            doc_to_add = Document(
                type=doc.type,
                id=doc.id,
                title=doc.title,
                url=doc.url,
                content=truncated_content,
                updated_at=doc.updated_at,
            )

            was_truncated = True
            has_truncation = True
            doc_tokens = count_tokens(truncated_content)

        if total_tokens + doc_tokens > _RETRIEVE_DOCUMENTS_MAX_TOKENS:
            remaining_tokens = _RETRIEVE_DOCUMENTS_MAX_TOKENS - total_tokens
            if remaining_tokens > 100:  # noqa: PLR2004
                truncated_content, original_tokens, truncated_tokens = _truncate_to_token_limit(
                    doc_to_add.content, remaining_tokens
                )
                percentage_preserved = round((truncated_tokens / original_tokens) * 100, 1)

                truncated_content += (
                    "\n\n[Content truncated due to global token limit. "
                    f"{percentage_preserved}% of original content preserved.]"
                )

                doc_to_add.content = truncated_content
                documents.append(doc_to_add)
                truncated_info.truncated_docs.append((doc.type, doc.id, doc.title))
                has_truncation = True
                total_tokens = _RETRIEVE_DOCUMENTS_MAX_TOKENS
            else:
                truncated_info.omitted_docs.append((doc.type, doc.id, doc.title))
                has_truncation = True
        else:
            documents.append(doc_to_add)
            total_tokens += doc_tokens
            if was_truncated:
                truncated_info.truncated_docs.append((doc.type, doc.id, doc.title))

    return (
        documents,
        not_found_ids if has_not_found_ids else None,
        truncated_info if has_truncation else None,
    )


async def _find_document_chunks_db(
    content_search_query: str,
    limit: int | None = 50,
    *,
    embedder: Embedder,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> list[DocumentChunkResult]:
    limit = 50
    with logfire.span(
        "create embedding for {content_search_query=}", content_search_query=content_search_query
    ) as span:
        is_ai = True
        span.set_attribute("app.is_ai", is_ai)
        result = await embedder.embed_query(content_search_query)

    assert len(result.embeddings) == 1, (
        f"Expected 1 embedding, got {len(result.embeddings)}, doc query: {content_search_query!r}"
    )
    embedding = result.embeddings[0]

    async with session_factory() as session:
        stmt = (
            select(
                DocumentContentChunk.content,
                DocumentContentChunk.sequence_number,
                DBDocument.type.label("document_type"),
                DBDocument.id_.label("document_id"),
                DBDocument.title.label("title"),
            )
            .join(DBDocument, DocumentContentChunk.document_id == DBDocument.id)
            .order_by(DocumentContentChunk.content_embedding.l2_distance(embedding))
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        rows = result.all()

        return [
            DocumentChunkResult(
                content=row.content,
                type=row.document_type,
                id=row.document_id,
                title=row.title,
                sequence_number=row.sequence_number,
            )
            for row in rows
        ]


async def _find_document_titles_db(
    title_search_query: str,
    limit: int | None = 100,
    *,
    embedder: Embedder,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> list[DocumentTitleResult]:
    limit = 100
    with logfire.span(
        "create embedding for {title_search_query=}", title_search_query=title_search_query
    ) as span:
        is_ai = True
        span.set_attribute("app.is_ai", is_ai)
        result = await embedder.embed_query(title_search_query)

    assert len(result.embeddings) == 1, (
        f"Expected 1 embedding, got {len(result.embeddings)}, doc query: {title_search_query!r}"
    )
    embedding = result.embeddings[0]

    async with session_factory() as session:
        stmt = select(DBDocument.title, DBDocument.type, DBDocument.id_).order_by(
            DBDocument.title_embedding.l2_distance(embedding)
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        rows = result.all()

        return [DocumentTitleResult(title=row.title, type=row.type, id=row.id_) for row in rows]


# PydanticAI tool wrappers with ctx argument and docstrings


async def retrieve_documents(
    ctx: RunContext[Deps],
    wp_page_ids: list[int] | None = None,
    wp_program_ids: list[int] | None = None,
    catalog_program_ids: list[int] | None = None,
    catalog_course_ids: list[int] | None = None,
) -> tuple[list[Document], NotFoundIds | None, TruncatedDocInfo | None]:
    """Retrieve full document content by IDs. Use other tools to get the IDs first."""
    return await _retrieve_documents_db(
        wp_page_ids=wp_page_ids,
        wp_program_ids=wp_program_ids,
        catalog_program_ids=catalog_program_ids,
        catalog_course_ids=catalog_course_ids,
        session_factory=ctx.deps.session_factory,
    )


async def find_document_titles(
    ctx: RunContext[Deps], title_search_query: str, limit: int | None = 100
) -> list[DocumentTitleResult]:
    """Retrieve document IDs and titles based on the title_search_query (via vector similarity matching).

    Results are sorted by vector similarity in descending order.
    """  # noqa: E501
    return await _find_document_titles_db(
        title_search_query,
        limit,
        embedder=ctx.deps.embedder,
        session_factory=ctx.deps.session_factory,
    )


async def find_document_chunks(
    ctx: RunContext[Deps], content_search_query: str, limit: int | None = 50
) -> list[DocumentChunkResult]:
    """Retrieve document text chunks based on the content_search_query (via vector similarity matching).

    Results are sorted by vector similarity in descending order.
    """  # noqa: E501
    return await _find_document_chunks_db(
        content_search_query,
        limit,
        embedder=ctx.deps.embedder,
        session_factory=ctx.deps.session_factory,
    )
