from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import logfire
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools.deps import Deps
from app.models import Document as DBDocument


async def _list_catalog_programs_db(
    *, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
) -> list[tuple[int, str]]:
    """Get all catalog program IDs and titles from database."""
    async with session_factory() as session:
        stmt = select(DBDocument.id_, DBDocument.title).where(DBDocument.type == "catalog_program")
        result = await session.execute(stmt)
        rows = result.all()
        return [(row.id_, row.title) for row in rows]


async def _list_catalog_courses_db(
    *, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
) -> list[tuple[int, str]]:
    """Get all catalog course IDs and titles from database."""
    async with session_factory() as session:
        stmt = select(DBDocument.id_, DBDocument.title).where(DBDocument.type == "catalog_course")
        result = await session.execute(stmt)
        rows = result.all()
        return [(row.id_, row.title) for row in rows]


async def list_catalog_programs(ctx: RunContext[Deps]) -> list[tuple[int, str]]:
    """Get catalog program IDs and titles."""
    with logfire.span("list_catalog_programs"):
        return await _list_catalog_programs_db(session_factory=ctx.deps.session_factory)


async def list_catalog_courses(ctx: RunContext[Deps]) -> list[tuple[int, str]]:
    """Get catalog course IDs and titles."""
    with logfire.span("list_catalog_courses"):
        return await _list_catalog_courses_db(session_factory=ctx.deps.session_factory)
