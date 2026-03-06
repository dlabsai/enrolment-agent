import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, TypeGuard
from uuid import UUID

from logfire._internal.constants import ATTRIBUTES_MESSAGE_KEY as LOGFIRE_ATTRIBUTES_MESSAGE_KEY
from logfire._internal.constants import (
    ATTRIBUTES_MESSAGE_TEMPLATE_KEY as LOGFIRE_ATTRIBUTES_MESSAGE_TEMPLATE_KEY,
)
from logfire._internal.formatter import logfire_format
from logfire._internal.scrubbing import NOOP_SCRUBBER as LOGFIRE_NOOP_SCRUBBER
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import get_tracer_provider
from opentelemetry.trace.span import format_span_id, format_trace_id
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import get_session
from app.models import OtelSpan

logger = logging.getLogger("va")

_background_tasks: set[asyncio.Task[None]] = set()
_span_processor_provider: object | None = None
_telemetry_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_is_ai(attributes: Mapping[str, Any] | None) -> bool:
    if not attributes:
        return False
    if attributes.get("app.is_ai") is True:
        return True
    return "gen_ai.request.model" in attributes


def _get_string_attr(attributes: Mapping[str, Any] | None, key: str) -> str | None:
    if not attributes:
        return None
    value = attributes.get(key)
    if value is None:
        return None
    return str(value)


def _get_int_attr(attributes: Mapping[str, Any] | None, key: str) -> int | None:
    if not attributes:
        return None
    value = attributes.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _get_float_attr(attributes: Mapping[str, Any] | None, key: str) -> float | None:
    if not attributes:
        return None
    value = attributes.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _get_uuid_attr(attributes: Mapping[str, Any] | None, key: str) -> UUID | None:
    if not attributes:
        return None
    value = attributes.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _get_bool_attr(attributes: Mapping[str, Any] | None, key: str) -> bool | None:
    if not attributes:
        return None
    value = attributes.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    value_str = str(value).strip().lower()
    if value_str in {"true", "1", "yes"}:
        return True
    if value_str in {"false", "0", "no"}:
        return False
    return None


def _format_span_name(span_name: str, attributes: Mapping[str, Any] | None) -> str:
    if not attributes:
        return span_name

    message = attributes.get(LOGFIRE_ATTRIBUTES_MESSAGE_KEY)
    if message is not None:
        return str(message)

    template_value = attributes.get(LOGFIRE_ATTRIBUTES_MESSAGE_TEMPLATE_KEY)
    template = str(template_value) if template_value is not None else span_name

    if "{" not in template:
        return template

    try:
        return logfire_format(template, dict(attributes), LOGFIRE_NOOP_SCRUBBER)
    except Exception:  # pragma: no cover - defensive guard
        return template


def _build_telemetry_database_url() -> str | None:
    url = os.getenv("TELEMETRY_DATABASE_URL")
    if not url:
        return None
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _get_telemetry_session_factory() -> async_sessionmaker[AsyncSession] | None:
    global _telemetry_session_factory  # noqa: PLW0603

    if _telemetry_session_factory is not None:
        return _telemetry_session_factory

    telemetry_url = _build_telemetry_database_url()
    if telemetry_url is None:
        return None

    engine = create_async_engine(telemetry_url, echo=False, poolclass=NullPool)
    _telemetry_session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    return _telemetry_session_factory


@asynccontextmanager
async def _get_otel_session() -> AsyncGenerator[AsyncSession]:
    session_factory = _get_telemetry_session_factory()
    if session_factory is None:
        async with get_session() as session:
            yield session
        return

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def configure_otel_span_processor() -> None:
    global _span_processor_provider  # noqa: PLW0603

    tracer_provider = get_tracer_provider()
    if tracer_provider is _span_processor_provider:
        return

    add_processor = getattr(tracer_provider, "add_span_processor", None)
    if add_processor is None:
        logger.warning("OpenTelemetry tracer provider does not support span processors")
        return

    add_processor(_DatabaseSpanProcessor())
    _span_processor_provider = tracer_provider


class _DatabaseSpanProcessor(SpanProcessor):
    def on_start(self, span: ReadableSpan, parent_context: object | None = None) -> None:
        # Required by SpanProcessor interface; intentionally unused.
        del span, parent_context

    def on_end(self, span: ReadableSpan) -> None:
        if span.end_time is None:
            return

        span_data = _span_to_payload(span)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_persist_span(span_data))
        else:
            task = loop.create_task(_persist_span(span_data))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        # Required by SpanProcessor interface; intentionally unused.
        del timeout_millis
        return True


async def _persist_span(span_data: dict[str, Any]) -> None:
    with suppress_instrumentation():
        async with _get_otel_session() as session:
            session.add(OtelSpan(**span_data))


def _span_to_payload(span: ReadableSpan) -> dict[str, Any]:
    start_time = _ns_to_datetime(span.start_time)
    end_time = _ns_to_datetime(span.end_time)
    duration_ms = None
    if span.end_time and span.start_time:
        duration_ms = (span.end_time - span.start_time) / 1_000_000

    attributes = _serialize_mapping(span.attributes)
    formatted_name = _format_span_name(span.name, span.attributes)
    is_ai = _get_is_ai(attributes)
    request_model = _get_string_attr(attributes, "gen_ai.request.model")
    provider_name = _get_string_attr(attributes, "gen_ai.provider.name")
    server_address = _get_string_attr(attributes, "server.address")
    input_tokens = _get_int_attr(attributes, "gen_ai.usage.input_tokens")
    output_tokens = _get_int_attr(attributes, "gen_ai.usage.output_tokens")
    total_cost = _get_float_attr(attributes, "operation.cost")
    conversation_id = _get_uuid_attr(attributes, "app.conversation_id")
    is_internal = _get_bool_attr(attributes, "app.is_internal")
    message_id = _get_uuid_attr(attributes, "app.message_id")
    total_time = _get_float_attr(attributes, "app.total_time")
    is_embedding = request_model is not None and "embedding" in request_model.lower()
    events = [
        {
            "name": event.name,
            "timestamp": _serialize_value(_ns_to_datetime(event.timestamp)),
            "attributes": _serialize_mapping(event.attributes),
        }
        for event in span.events
    ]
    links: list[dict[str, Any]] = []
    for link in span.links:
        context = link.context
        links.append(
            {
                "trace_id": format_trace_id(context.trace_id),
                "span_id": format_span_id(context.span_id),
                "attributes": _serialize_mapping(link.attributes),
            }
        )

    instrumentation_scope = span.instrumentation_scope
    scope = None
    if instrumentation_scope is not None:
        scope = {
            "name": instrumentation_scope.name,
            "version": instrumentation_scope.version,
            "schema_url": instrumentation_scope.schema_url,
        }

    resource = {
        "attributes": _serialize_mapping(span.resource.attributes),
        "schema_url": span.resource.schema_url,
    }

    parent_span_id = None
    if span.parent is not None:
        parent_span_id = format_span_id(span.parent.span_id)

    status_code = span.status.status_code.name
    status_message = span.status.description

    span_context = span.context
    if span_context is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Span context missing")

    span_time = start_time or datetime.now(tz=UTC)

    return {
        "trace_id": format_trace_id(span_context.trace_id),
        "span_id": format_span_id(span_context.span_id),
        "parent_span_id": parent_span_id,
        "name": formatted_name,
        "kind": span.kind.name,
        "status_code": status_code,
        "status_message": status_message,
        "start_time": start_time,
        "end_time": end_time,
        "span_time": span_time,
        "duration_ms": duration_ms,
        "attributes": attributes,
        "request_model": request_model,
        "provider_name": provider_name,
        "server_address": server_address,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_cost": total_cost,
        "is_embedding": is_embedding,
        "conversation_id": conversation_id,
        "is_internal": is_internal,
        "message_id": message_id,
        "total_time": total_time,
        "is_ai": is_ai,
        "events": events or None,
        "links": links or None,
        "resource": resource,
        "scope": scope,
    }


def _serialize_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not mapping:
        return None
    return {str(key): _serialize_value(value) for key, value in mapping.items()}


def _is_mapping(value: Any) -> TypeGuard[Mapping[str, Any]]:
    return isinstance(value, Mapping)


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if _is_mapping(value):
        return {str(key): _serialize_value(val) for key, val in value.items()}
    if _is_sequence(value):
        return [_serialize_value(item) for item in value]
    return str(value)


def _ns_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)


def span_to_payload(span: ReadableSpan) -> dict[str, Any]:
    return _span_to_payload(span)


def get_database_span_processor() -> SpanProcessor:
    return _DatabaseSpanProcessor()


async def persist_span(span_data: dict[str, Any]) -> None:
    await _persist_span(span_data)


async def wait_for_pending_spans() -> None:
    tasks = list(_background_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
