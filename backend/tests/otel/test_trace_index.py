from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.usage import get_trace_index
from app.api.schemas import PaginationParams
from app.models import OtelSpan, User, UserRole


@pytest.mark.asyncio
async def test_trace_index_ai_only_filters(session: AsyncSession) -> None:
    now = datetime.now(UTC)

    ai_trace_id = "trace-ai"
    non_ai_trace_id = "trace-non-ai"

    admin_user = User(
        email="admin-ai@example.com",
        name="Admin",
        password_hash="test",  # noqa: S106
        is_active=True,
        role=UserRole.ADMIN,
    )

    session.add_all(
        [
            admin_user,
            OtelSpan(
                trace_id=ai_trace_id,
                span_id="span-ai",
                parent_span_id=None,
                name="chat gpt-5.1",
                kind="INTERNAL",
                status_code="OK",
                status_message=None,
                start_time=now,
                end_time=now + timedelta(milliseconds=120),
                duration_ms=120.0,
                is_ai=True,
                request_model="gpt-5.1",
                attributes={
                    "gen_ai.input.messages": '[{"role":"user","content":"hi"}]',
                    "gen_ai.request.model": "gpt-5.1",
                },
            ),
            OtelSpan(
                trace_id=non_ai_trace_id,
                span_id="span-non-ai",
                parent_span_id=None,
                name="GET /api/auth/me",
                kind="SERVER",
                status_code="OK",
                status_message=None,
                start_time=now,
                end_time=now + timedelta(milliseconds=50),
                duration_ms=50.0,
                attributes={"http.method": "GET"},
            ),
        ]
    )
    await session.flush()

    page_params = PaginationParams()

    all_traces_page = await get_trace_index(session, page_params=page_params, ai_only=False)
    ai_only_traces_page = await get_trace_index(session, page_params=page_params, ai_only=True)

    all_traces = all_traces_page.items
    ai_only_traces = ai_only_traces_page.items

    assert {trace.trace_id for trace in all_traces} >= {ai_trace_id, non_ai_trace_id}
    assert [trace.trace_id for trace in ai_only_traces] == [ai_trace_id]
    assert ai_only_traces[0].is_ai is True
