from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import otel
from app.models import OtelSpan


@dataclass
class DummyStatusCode:
    name: str


@dataclass
class DummyStatus:
    status_code: DummyStatusCode
    description: str | None


@dataclass
class DummyKind:
    name: str


@dataclass
class DummyContext:
    trace_id: int
    span_id: int


@dataclass
class DummyParent:
    span_id: int


@dataclass
class DummyEvent:
    name: str
    timestamp: int
    attributes: dict[str, Any] | None


@dataclass
class DummyLink:
    context: DummyContext
    attributes: dict[str, Any] | None


@dataclass
class DummyScope:
    name: str
    version: str | None
    schema_url: str | None


@dataclass
class DummyResource:
    attributes: dict[str, Any]
    schema_url: str | None


@dataclass
class DummySpan:
    name: str
    kind: DummyKind
    status: DummyStatus
    start_time: int
    end_time: int
    attributes: dict[str, Any] | None
    events: list[DummyEvent]
    links: list[DummyLink]
    instrumentation_scope: DummyScope | None
    resource: DummyResource
    parent: DummyParent | None
    context: DummyContext


def _build_dummy_span() -> DummySpan:
    return DummySpan(
        name="chat completion",
        kind=DummyKind(name="INTERNAL"),
        status=DummyStatus(status_code=DummyStatusCode(name="OK"), description="all good"),
        start_time=1_000_000_000,
        end_time=2_500_000_000,
        attributes={"app.conversation_id": "conv-123", "list": [1, "two"], "nested": {"value": 3}},
        events=[
            DummyEvent(name="gen_ai.message", timestamp=1_200_000_000, attributes={"role": "user"})
        ],
        links=[
            DummyLink(
                context=DummyContext(trace_id=0x1234, span_id=0x5678), attributes={"link": True}
            )
        ],
        instrumentation_scope=DummyScope(
            name="pydantic-ai",
            version="1.0.0",
            schema_url="https://opentelemetry.io/schemas/1.37.0",
        ),
        resource=DummyResource(attributes={"service.name": "va"}, schema_url=None),
        parent=DummyParent(span_id=0x9ABC),
        context=DummyContext(
            trace_id=0x11112222333344445555666677778888, span_id=0x1A2B3C4D5E6F7788
        ),
    )


def test_span_to_payload_serialization() -> None:
    payload = otel.span_to_payload(cast(ReadableSpan, _build_dummy_span()))

    assert payload["trace_id"]
    assert payload["span_id"]
    assert payload["parent_span_id"] == "0000000000009abc"
    assert payload["name"] == "chat completion"
    assert payload["kind"] == "INTERNAL"
    assert payload["status_code"] == "OK"
    assert payload["status_message"] == "all good"
    assert payload["duration_ms"] == 1500.0
    assert payload["attributes"] == {
        "app.conversation_id": "conv-123",
        "list": [1, "two"],
        "nested": {"value": 3},
    }
    assert payload["events"][0]["name"] == "gen_ai.message"
    assert payload["links"][0]["span_id"] == "0000000000005678"
    assert payload["resource"]["attributes"]["service.name"] == "va"


@pytest.mark.asyncio
async def test_persist_span_writes_row(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    @asynccontextmanager
    async def _fake_get_session() -> AsyncGenerator[AsyncSession]:
        yield session
        await session.flush()

    monkeypatch.setattr("app.otel.get_session", _fake_get_session)

    payload = otel.span_to_payload(cast(ReadableSpan, _build_dummy_span()))
    await otel.persist_span(payload)

    result = await session.execute(
        select(OtelSpan).where(
            OtelSpan.trace_id == payload["trace_id"], OtelSpan.span_id == payload["span_id"]
        )
    )
    span = result.scalar_one()

    assert span.trace_id == payload["trace_id"]
    assert span.span_id == payload["span_id"]
    assert span.attributes == payload["attributes"]
