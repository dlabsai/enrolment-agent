from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Result, String, Uuid, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import count

from app.api.schemas import BaseFilters, PageOut, PaginationParams
from app.models import Base


async def get_paginated_results[T: Base, R: BaseModel](
    session: AsyncSession,
    db_model: type[T],
    response_model: type[R],
    pagination_params: PaginationParams,
    filters: BaseFilters,
    base_statement: Select[tuple[Any, ...]] | None = None,
    process_results: Callable[[Result[tuple[Any, ...]]], list[R]] | None = None,
) -> PageOut[R]:
    statement = select(db_model) if base_statement is None else base_statement

    filters_ = {
        name: value
        for name, value in filters.__dict__.items()
        if value is not None and name != "search"
    }

    global_conditions = {}
    conditions = {}
    if filters.search:
        global_conditions = {
            name: filters.search
            for name in filters.__dict__
            if not name.endswith("_id") and name != "search"
        }
    conditions = filters_

    statement = statement.where(or_(*_get_conditions(global_conditions, db_model)))
    statement = statement.where(*_get_conditions(conditions, db_model))

    count_statement = select(count()).select_from(statement.subquery())
    total_count = (await session.execute(count_statement)).scalar() or 0

    if pagination_params.sort_by:
        sort_column = _get_column(pagination_params.sort_by, db_model)
        if sort_column is not None:
            statement = statement.order_by(
                sort_column.desc() if pagination_params.descending else sort_column
            )

    statement = statement.offset(pagination_params.offset)
    if pagination_params.limit:
        statement = statement.limit(pagination_params.limit)

    return PageOut[R](
        items=process_results(await session.execute(statement))
        if process_results
        else [
            response_model.model_validate(row)
            for row in (await session.execute(statement)).scalars()
        ],
        total=total_count,
    )


def _get_column[T: Base](name: str, db_model: type[T]) -> ColumnElement[Any] | None:
    if name not in db_model.__table__.columns:
        return None
    return db_model.__table__.columns[name]


def _get_conditions[T: Base](
    filters: dict[str, Any], db_model: type[T]
) -> list[ColumnElement[Any]]:
    conditions: list[ColumnElement[Any]] = []
    for name, value in filters.items():
        column = _get_column(name, db_model)
        if column is None:
            continue
        column_type = column.type
        if isinstance(column_type, String):
            conditions.append(column.ilike(f"%{value}%"))
        elif name.endswith("id") and isinstance(column_type, Uuid):
            try:
                uuid_obj = UUID(str(value))
                conditions.append(column == uuid_obj)
            except ValueError:
                conditions.append(func.cast(column, String).ilike(f"%{value}%"))
        else:
            conditions.append(column == value)
    return conditions
