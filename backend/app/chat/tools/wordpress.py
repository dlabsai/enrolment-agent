from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import logfire
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools.deps import Deps
from app.models import Document as DBDocument


async def _list_pages_db(
    *, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
) -> list[tuple[int, str]]:
    """Get all WordPress page IDs and titles from database."""
    async with session_factory() as session:
        stmt = select(DBDocument.id_, DBDocument.title).where(DBDocument.type == "wp_page")
        result = await session.execute(stmt)
        rows = result.all()
        return [(row.id_, row.title) for row in rows]


async def _list_programs_db(
    *, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
) -> list[tuple[int, str]]:
    """Get all WordPress program IDs and titles from database."""
    async with session_factory() as session:
        stmt = select(DBDocument.id_, DBDocument.title).where(DBDocument.type == "wp_program")
        result = await session.execute(stmt)
        rows = result.all()
        return [(row.id_, row.title) for row in rows]


# PydanticAI tool wrappers with ctx argument and docstrings


async def list_wordpress_pages(ctx: RunContext[Deps]) -> list[tuple[int, str]]:
    """Get WordPress page IDs and titles."""
    with logfire.span("list_wordpress_pages"):
        return await _list_pages_db(session_factory=ctx.deps.session_factory)


async def list_wordpress_programs(ctx: RunContext[Deps]) -> list[tuple[int, str]]:
    """Get WordPress program IDs and titles."""
    with logfire.span("list_wordpress_programs"):
        return await _list_programs_db(session_factory=ctx.deps.session_factory)
