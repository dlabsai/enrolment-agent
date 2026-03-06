from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Float, Integer, String, case, cast, func, or_, select
from sqlalchemy.sql import ColumnElement

from app.api.deps import SessionDep, get_current_user, require_user_roles
from app.api.schemas import (
    PageOut,
    PaginationParams,
    TraceDetailOut,
    TraceSpanOut,
    TraceSummaryOut,
    UsageDailyOut,
    UsageModelOut,
    UsageOverviewOut,
    UsageSummaryOut,
    UsageTraceBasicOut,
)
from app.models import Conversation, OtelSpan, UserRole

router = APIRouter(
    prefix="/usage",
    tags=["usage"],
    dependencies=[Depends(require_user_roles(get_current_user, UserRole.ADMIN, UserRole.DEV))],
)


def _use_hourly_buckets(start: datetime | None, end: datetime | None) -> bool:
    return start is not None and end is not None and end - start <= timedelta(hours=24)


def _build_usage_daily_data(
    rows: Iterable[Any], start: datetime | None, end: datetime | None, *, use_hourly: bool
) -> list[UsageDailyOut]:
    if not use_hourly or start is None or end is None:
        return [
            UsageDailyOut(
                date=row.date,
                requests=row.requests,
                tokens=row.tokens,
                cost=float(row.cost),
                embedding_requests=row.embedding_requests,
                embedding_tokens=row.embedding_tokens,
                embedding_cost=float(row.embedding_cost),
                errors=row.errors,
                avg_duration=float(row.avg_duration or 0),
            )
            for row in rows
        ]

    row_map = {row.date: row for row in rows}
    current = start.replace(minute=0, second=0, microsecond=0)
    end_bucket = end.replace(minute=0, second=0, microsecond=0)
    hourly_rows: list[UsageDailyOut] = []
    while current <= end_bucket:
        row = row_map.get(current)
        if row is None:
            hourly_rows.append(
                UsageDailyOut(
                    date=current,
                    requests=0,
                    tokens=0,
                    cost=0.0,
                    embedding_requests=0,
                    embedding_tokens=0,
                    embedding_cost=0.0,
                    errors=0,
                    avg_duration=0.0,
                )
            )
        else:
            hourly_rows.append(
                UsageDailyOut(
                    date=row.date,
                    requests=row.requests,
                    tokens=row.tokens,
                    cost=float(row.cost),
                    embedding_requests=row.embedding_requests,
                    embedding_tokens=row.embedding_tokens,
                    embedding_cost=float(row.embedding_cost),
                    errors=row.errors,
                    avg_duration=float(row.avg_duration or 0),
                )
            )
        current += timedelta(hours=1)

    return hourly_rows


def _format_model_display(model: str, provider: str | None, server: str | None) -> str:
    if provider == "azure":
        return f"azure:{model}"
    if provider == "openrouter":
        return f"openrouter:{model}"
    if provider == "openai":
        if server == "openrouter.ai":
            return f"openrouter:{model}"
        return f"openai:{model}"
    return model


def _format_model_from_attributes(attributes: dict[str, Any]) -> str | None:
    model_value = attributes.get("gen_ai.request.model")
    if model_value is None:
        return None
    provider_value = attributes.get("gen_ai.provider.name")
    server_value = attributes.get("server.address")
    provider = str(provider_value) if provider_value is not None else None
    server = str(server_value) if server_value is not None else None
    return _format_model_display(str(model_value), provider, server)


def _format_model_from_span(span: OtelSpan) -> str | None:
    if span.request_model is not None:
        return _format_model_display(span.request_model, span.provider_name, span.server_address)
    attributes = span.attributes or {}
    return _format_model_from_attributes(attributes)


def _build_model_filter(
    model_expr: ColumnElement[str], models: Iterable[str] | None
) -> ColumnElement[bool] | None:
    if not models:
        return None
    provider_prefixes = {"openrouter", "openai", "azure"}
    filters: list[ColumnElement[bool]] = []
    for raw_value in models:
        value = raw_value.strip()
        if value == "":
            continue
        value = value.removesuffix(":")
        if value in provider_prefixes:
            filters.append(model_expr.ilike(f"{value}:%"))
        else:
            filters.append(model_expr == value)
    if not filters:
        return None
    return or_(*filters)


async def _resolve_trace_context(
    session: SessionDep, trace_ids: Iterable[str] | None = None
) -> tuple[dict[str, bool | None], dict[str, UUID | None]]:
    trace_context_stmt = select(
        OtelSpan.trace_id, OtelSpan.conversation_id, OtelSpan.is_internal
    ).where(or_(OtelSpan.conversation_id.is_not(None), OtelSpan.is_internal.is_not(None)))
    if trace_ids is not None:
        trace_context_stmt = trace_context_stmt.where(OtelSpan.trace_id.in_(trace_ids))

    trace_context_result = await session.execute(trace_context_stmt)
    context_rows = trace_context_result.all()

    conversation_ids: set[UUID] = {
        conversation_id
        for _trace_id, conversation_id, _is_internal in context_rows
        if conversation_id is not None
    }
    trace_conversation_map: dict[str, UUID | None] = {}
    for trace_id, conversation_id, _is_internal in context_rows:
        if conversation_id is not None:
            trace_conversation_map.setdefault(str(trace_id), conversation_id)

    conversation_public_map: dict[UUID, bool] = {}
    if conversation_ids:
        conversation_result = await session.execute(
            select(Conversation.id, Conversation.is_public).where(
                Conversation.id.in_(conversation_ids)
            )
        )
        conversation_public_map = {}
        for conversation_id, is_public in conversation_result.all():
            conversation_public_map[conversation_id] = is_public

    trace_public_map: dict[str, bool | None] = {}
    for trace_id, conversation_id, is_internal in context_rows:
        if is_internal is not None:
            trace_public_map.setdefault(str(trace_id), not bool(is_internal))
            continue
        if conversation_id is not None and conversation_id in conversation_public_map:
            trace_public_map.setdefault(str(trace_id), conversation_public_map[conversation_id])

    return trace_public_map, trace_conversation_map


@router.get("/summary", response_model=UsageOverviewOut)
async def get_usage_summary(
    session: SessionDep,
    platform: Annotated[str | None, Query()] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    models: Annotated[list[str] | None, Query()] = None,
    latest_limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> Any:
    if platform not in {None, "both", "internal", "public"}:
        raise HTTPException(status_code=400, detail="Invalid platform")

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="Invalid time range")

    platform_value = "both" if platform in (None, "both") else platform

    span_time_expr: ColumnElement[datetime] = func.coalesce(
        OtelSpan.span_time, OtelSpan.start_time, OtelSpan.created_at
    )
    base_model_expr: ColumnElement[str] = cast(OtelSpan.request_model, String)
    provider_expr: ColumnElement[str] = cast(OtelSpan.provider_name, String)
    server_expr: ColumnElement[str] = cast(OtelSpan.server_address, String)
    model_expr: ColumnElement[str] = case(
        (provider_expr == "azure", func.concat("azure:", base_model_expr)),
        (provider_expr == "openrouter", func.concat("openrouter:", base_model_expr)),
        (
            (provider_expr == "openai") & (server_expr == "openrouter.ai"),
            func.concat("openrouter:", base_model_expr),
        ),
        (provider_expr == "openai", func.concat("openai:", base_model_expr)),
        else_=base_model_expr,
    )
    input_tokens_expr: ColumnElement[int] = cast(OtelSpan.input_tokens, Integer)
    output_tokens_expr: ColumnElement[int] = cast(OtelSpan.output_tokens, Integer)
    tokens_expr: ColumnElement[int] = func.coalesce(input_tokens_expr, 0) + func.coalesce(
        output_tokens_expr, 0
    )
    cost_expr: ColumnElement[float] = cast(OtelSpan.total_cost, Float)
    duration_expr: ColumnElement[float | None] = case(
        (OtelSpan.duration_ms.is_not(None), OtelSpan.duration_ms / 1000.0), else_=None
    )
    is_embedding_expr: ColumnElement[bool] = func.coalesce(OtelSpan.is_embedding, False)
    is_error_expr: ColumnElement[bool] = OtelSpan.status_code == "ERROR"

    filters: list[Any] = [OtelSpan.request_model.is_not(None), OtelSpan.is_ai.is_(True)]
    if start is not None:
        filters.append(span_time_expr >= start)
    if end is not None:
        filters.append(span_time_expr <= end)
    model_filter = _build_model_filter(model_expr, models)
    if model_filter is not None:
        filters.append(model_filter)

    trace_context_subquery = None
    platform_filter = None

    if platform_value in {"internal", "public"}:
        trace_context_subquery = (
            select(
                OtelSpan.trace_id.label("trace_id"),
                func.max(OtelSpan.conversation_id).label("conversation_id"),
                func.bool_or(OtelSpan.is_internal).label("is_internal"),
            )
            .where(or_(OtelSpan.conversation_id.is_not(None), OtelSpan.is_internal.is_not(None)))
            .group_by(OtelSpan.trace_id)
            .subquery()
        )

        is_public_expr = case(
            (
                trace_context_subquery.c.is_internal.is_not(None),
                ~trace_context_subquery.c.is_internal,
            ),
            (Conversation.is_public.is_not(None), Conversation.is_public),
            else_=None,
        )
        is_public_filter_expr = func.coalesce(is_public_expr, False)
        platform_filter = is_public_filter_expr.is_(platform_value == "public")

    def apply_platform_filters(statement: Any) -> Any:
        if trace_context_subquery is None:
            return statement
        return statement.outerjoin(
            trace_context_subquery, trace_context_subquery.c.trace_id == OtelSpan.trace_id
        ).outerjoin(Conversation, Conversation.id == trace_context_subquery.c.conversation_id)

    use_hourly_buckets = _use_hourly_buckets(start, end)
    bucket_unit = "hour" if use_hourly_buckets else "day"
    time_bucket = func.date_trunc(bucket_unit, span_time_expr)
    daily_stmt = select(
        time_bucket.label("date"),
        func.coalesce(func.sum(case((~is_embedding_expr, 1), else_=0)), 0).label("requests"),
        func.coalesce(func.sum(case((~is_embedding_expr, tokens_expr), else_=0)), 0).label(
            "tokens"
        ),
        func.coalesce(
            func.sum(case((~is_embedding_expr, func.coalesce(cost_expr, 0.0)), else_=0.0)), 0.0
        ).label("cost"),
        func.coalesce(func.sum(case((is_embedding_expr, 1), else_=0)), 0).label(
            "embedding_requests"
        ),
        func.coalesce(func.sum(case((is_embedding_expr, tokens_expr), else_=0)), 0).label(
            "embedding_tokens"
        ),
        func.coalesce(
            func.sum(case((is_embedding_expr, func.coalesce(cost_expr, 0.0)), else_=0.0)), 0.0
        ).label("embedding_cost"),
        func.coalesce(func.sum(case(((~is_embedding_expr) & is_error_expr, 1), else_=0)), 0).label(
            "errors"
        ),
        func.avg(case((~is_embedding_expr, duration_expr), else_=None)).label("avg_duration"),
    ).select_from(OtelSpan)

    daily_stmt = apply_platform_filters(daily_stmt).where(*filters)
    if platform_filter is not None:
        daily_stmt = daily_stmt.where(platform_filter)
    daily_stmt = daily_stmt.group_by(time_bucket).order_by(time_bucket)

    daily_result = await session.execute(daily_stmt)
    daily_rows = daily_result.all()
    daily_data = _build_usage_daily_data(daily_rows, start, end, use_hourly=use_hourly_buckets)

    summary_stmt = select(
        func.coalesce(func.sum(case((~is_embedding_expr, 1), else_=0)), 0).label("total_requests"),
        func.coalesce(func.sum(case((~is_embedding_expr, tokens_expr), else_=0)), 0).label(
            "total_tokens"
        ),
        func.coalesce(
            func.sum(case((~is_embedding_expr, func.coalesce(cost_expr, 0.0)), else_=0.0)), 0.0
        ).label("total_cost"),
        func.coalesce(func.sum(case((is_embedding_expr, 1), else_=0)), 0).label(
            "total_embedding_requests"
        ),
        func.coalesce(func.sum(case((is_embedding_expr, tokens_expr), else_=0)), 0).label(
            "total_embedding_tokens"
        ),
        func.coalesce(
            func.sum(case((is_embedding_expr, func.coalesce(cost_expr, 0.0)), else_=0.0)), 0.0
        ).label("total_embedding_cost"),
        func.avg(case((is_embedding_expr, duration_expr), else_=None)).label(
            "total_embedding_avg_duration"
        ),
        func.coalesce(func.sum(case(((~is_embedding_expr) & is_error_expr, 1), else_=0)), 0).label(
            "total_errors"
        ),
        func.avg(case((~is_embedding_expr, duration_expr), else_=None)).label("avg_duration"),
    ).select_from(OtelSpan)

    summary_stmt = apply_platform_filters(summary_stmt).where(*filters)
    if platform_filter is not None:
        summary_stmt = summary_stmt.where(platform_filter)

    summary_result = await session.execute(summary_stmt)
    summary_row = summary_result.one()

    model_stmt = select(
        model_expr.label("model"),
        func.count(OtelSpan.id).label("requests"),
        func.coalesce(func.sum(tokens_expr), 0).label("tokens"),
        func.coalesce(func.sum(func.coalesce(cost_expr, 0.0)), 0.0).label("cost"),
    ).select_from(OtelSpan)

    model_stmt = apply_platform_filters(model_stmt).where(*filters)
    if platform_filter is not None:
        model_stmt = model_stmt.where(platform_filter)
    model_stmt = model_stmt.group_by(model_expr).order_by(func.count(OtelSpan.id).desc())

    model_result = await session.execute(model_stmt)
    model_rows = model_result.all()

    span_stmt = select(OtelSpan)
    span_stmt = apply_platform_filters(span_stmt).where(*filters)
    if platform_filter is not None:
        span_stmt = span_stmt.where(platform_filter)
    span_stmt = span_stmt.order_by(span_time_expr.desc()).limit(latest_limit)

    span_result = await session.execute(span_stmt)
    spans = span_result.scalars().all()

    trace_ids = [span.trace_id for span in spans]
    trace_public_map: dict[str, bool | None] = {}
    if trace_ids:
        trace_public_map, _trace_conversation_map = await _resolve_trace_context(
            session, trace_ids=trace_ids
        )

    latest_traces: list[UsageTraceBasicOut] = []
    for span in spans:
        model_value = _format_model_from_span(span)
        if model_value is None:
            continue
        latest_traces.append(
            UsageTraceBasicOut(
                created_at=span.start_time or span.created_at,
                model=model_value,
                prompt_tokens=span.input_tokens,
                completion_tokens=span.output_tokens,
                cost=span.total_cost,
                duration=(span.duration_ms / 1000.0) if span.duration_ms is not None else None,
                is_error=span.status_code == "ERROR",
                is_public=trace_public_map.get(span.trace_id),
            )
        )

    return UsageOverviewOut(
        summary=UsageSummaryOut(
            total_requests=summary_row.total_requests,
            total_tokens=summary_row.total_tokens,
            total_cost=float(summary_row.total_cost),
            total_embedding_requests=summary_row.total_embedding_requests,
            total_embedding_tokens=summary_row.total_embedding_tokens,
            total_embedding_cost=float(summary_row.total_embedding_cost),
            total_embedding_avg_duration=float(summary_row.total_embedding_avg_duration or 0),
            total_errors=summary_row.total_errors,
            avg_duration=float(summary_row.avg_duration or 0),
        ),
        daily=daily_data,
        models=[
            UsageModelOut(
                model=row.model, requests=row.requests, tokens=row.tokens, cost=float(row.cost)
            )
            for row in model_rows
        ],
        latest_traces=latest_traces,
    )


@router.get("/trace-index", response_model=PageOut[TraceSummaryOut])
async def get_trace_index(
    session: SessionDep,
    page_params: Annotated[PaginationParams, Depends()],
    ai_only: Annotated[bool, Query()] = False,
    platform: Annotated[str | None, Query()] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> Any:
    if platform not in {None, "both", "internal", "public"}:
        raise HTTPException(status_code=400, detail="Invalid platform")

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="Invalid time range")

    span_time_expr = func.coalesce(OtelSpan.span_time, OtelSpan.start_time, OtelSpan.created_at)
    latest_start = func.max(span_time_expr).label("latest_start")
    started_at = func.min(span_time_expr).label("started_at")
    ended_at = func.max(func.coalesce(OtelSpan.end_time, OtelSpan.created_at)).label("ended_at")
    span_count = func.count(OtelSpan.id).label("span_count")

    summary_stmt = select(
        OtelSpan.trace_id, started_at, ended_at, span_count, latest_start
    ).group_by(OtelSpan.trace_id)

    if ai_only:
        ai_trace_ids_stmt = (
            select(func.distinct(OtelSpan.trace_id).label("trace_id"))
            .where(OtelSpan.is_ai.is_(True))
            .subquery()
        )
        summary_stmt = summary_stmt.where(
            OtelSpan.trace_id.in_(select(ai_trace_ids_stmt.c.trace_id))
        )

    if platform in {"internal", "public"}:
        trace_context_subquery = (
            select(
                OtelSpan.trace_id.label("trace_id"),
                func.max(OtelSpan.conversation_id).label("conversation_id"),
                func.bool_or(OtelSpan.is_internal).label("is_internal"),
            )
            .where(or_(OtelSpan.conversation_id.is_not(None), OtelSpan.is_internal.is_not(None)))
            .group_by(OtelSpan.trace_id)
            .subquery()
        )

        is_public_expr = case(
            (
                trace_context_subquery.c.is_internal.is_not(None),
                ~trace_context_subquery.c.is_internal,
            ),
            (Conversation.is_public.is_not(None), Conversation.is_public),
            else_=False,
        )

        summary_stmt = summary_stmt.outerjoin(
            trace_context_subquery, trace_context_subquery.c.trace_id == OtelSpan.trace_id
        ).outerjoin(Conversation, Conversation.id == trace_context_subquery.c.conversation_id)

        if platform == "public":
            summary_stmt = summary_stmt.where(is_public_expr.is_(True))
        else:
            summary_stmt = summary_stmt.where(is_public_expr.is_(False))

    if start is not None:
        summary_stmt = summary_stmt.having(started_at >= start)
    if end is not None:
        summary_stmt = summary_stmt.having(started_at <= end)

    count_stmt = select(func.count()).select_from(summary_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    duration_expr = func.extract("epoch", ended_at - started_at)
    sort_map = {
        "started_at": started_at,
        "ended_at": ended_at,
        "latest_start": latest_start,
        "span_count": span_count,
        "duration_ms": duration_expr,
    }
    sort_column = sort_map.get(page_params.sort_by, latest_start)
    summary_stmt = summary_stmt.order_by(
        sort_column.desc() if page_params.descending else sort_column.asc()
    )

    summary_stmt = summary_stmt.offset(page_params.offset)
    if page_params.limit:
        summary_stmt = summary_stmt.limit(page_params.limit)

    summary_result = await session.execute(summary_stmt)
    summary_rows = summary_result.all()

    trace_ids = [row.trace_id for row in summary_rows]
    if not trace_ids:
        return PageOut[TraceSummaryOut](items=[], total=total)

    trace_public_map, trace_conversation_map = await _resolve_trace_context(
        session, trace_ids=trace_ids
    )

    root_name_expr = func.max(
        case((OtelSpan.parent_span_id.is_(None), OtelSpan.name), else_=None)
    ).label("root_span_name")
    error_expr = func.bool_or(OtelSpan.status_code == "ERROR").label("is_error")
    ai_expr = func.bool_or(OtelSpan.is_ai).label("is_ai")
    request_model_expr = func.max(OtelSpan.request_model).label("request_model")
    provider_expr = func.max(OtelSpan.provider_name).label("provider_name")
    server_expr = func.max(OtelSpan.server_address).label("server_address")

    span_meta_stmt = (
        select(
            OtelSpan.trace_id,
            root_name_expr,
            error_expr,
            ai_expr,
            request_model_expr,
            provider_expr,
            server_expr,
        )
        .where(OtelSpan.trace_id.in_(trace_ids))
        .group_by(OtelSpan.trace_id)
    )
    span_meta_rows = (await session.execute(span_meta_stmt)).all()

    trace_model_map: dict[str, str] = {}
    trace_root_map: dict[str, str] = {}
    trace_error_map: dict[str, bool] = {}
    trace_ai_map: dict[str, bool] = {}

    for row in span_meta_rows:
        trace_id = row.trace_id
        if row.root_span_name is not None:
            trace_root_map[trace_id] = row.root_span_name
        if row.is_error:
            trace_error_map[trace_id] = True
        if row.is_ai:
            trace_ai_map[trace_id] = True
        if row.request_model is not None:
            model = _format_model_display(row.request_model, row.provider_name, row.server_address)
            trace_model_map[trace_id] = model

    results: list[TraceSummaryOut] = []
    for row in summary_rows:
        duration_ms = None
        if row.started_at and row.ended_at:
            duration_ms = (row.ended_at - row.started_at).total_seconds() * 1000
        results.append(
            TraceSummaryOut(
                trace_id=row.trace_id,
                started_at=row.started_at,
                duration_ms=duration_ms,
                span_count=row.span_count,
                root_span_name=trace_root_map.get(row.trace_id),
                model=trace_model_map.get(row.trace_id),
                is_error=trace_error_map.get(row.trace_id, False),
                is_public=trace_public_map.get(row.trace_id),
                conversation_id=trace_conversation_map.get(row.trace_id),
                is_ai=trace_ai_map.get(row.trace_id, False),
            )
        )

    return PageOut[TraceSummaryOut](items=results, total=total)


async def _build_trace_detail(trace_id: str, session: SessionDep) -> TraceDetailOut:
    span_result = await session.execute(
        select(OtelSpan).where(OtelSpan.trace_id == trace_id).order_by(OtelSpan.start_time.asc())
    )
    spans = span_result.scalars().all()
    if not spans:
        raise HTTPException(status_code=404, detail="Trace not found")

    start_times = [span.start_time or span.created_at for span in spans]
    end_times = [span.end_time or span.created_at for span in spans]

    started_at = min(start_times) if start_times else None
    ended_at = max(end_times) if end_times else None

    duration_ms = None
    if started_at and ended_at:
        duration_ms = (ended_at - started_at).total_seconds() * 1000

    trace_public_map, trace_conversation_map = await _resolve_trace_context(
        session, trace_ids=[trace_id]
    )

    return TraceDetailOut(
        trace_id=trace_id,
        started_at=started_at,
        duration_ms=duration_ms,
        span_count=len(spans),
        is_public=trace_public_map.get(trace_id),
        conversation_id=trace_conversation_map.get(trace_id),
        spans=[
            TraceSpanOut(
                span_id=span.span_id,
                parent_span_id=span.parent_span_id,
                name=span.name,
                kind=span.kind,
                status_code=span.status_code,
                status_message=span.status_message,
                start_time=span.start_time,
                end_time=span.end_time,
                duration_ms=span.duration_ms,
                attributes=span.attributes,
                events=span.events,
                links=span.links,
                resource=span.resource,
                scope=span.scope,
            )
            for span in spans
        ],
    )


@router.get("/trace/{trace_id}", response_model=TraceDetailOut)
async def get_trace_detail(trace_id: str, session: SessionDep) -> Any:
    return await _build_trace_detail(trace_id, session)


@router.get("/trace-by-message/{message_id}", response_model=TraceDetailOut)
async def get_trace_detail_by_message_id(message_id: UUID, session: SessionDep) -> Any:
    span_time_expr = func.coalesce(OtelSpan.span_time, OtelSpan.start_time, OtelSpan.created_at)
    trace_id_result = await session.execute(
        select(OtelSpan.trace_id)
        .where(OtelSpan.message_id == message_id)
        .order_by(span_time_expr.desc())
        .limit(1)
    )
    trace_id_row = trace_id_result.first()
    if trace_id_row is None:
        raise HTTPException(status_code=404, detail="Trace not found for message")

    return await _build_trace_detail(trace_id_row.trace_id, session)
