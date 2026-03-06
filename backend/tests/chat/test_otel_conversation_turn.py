import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import otel
from app.chat.engine import handle_conversation_turn
from app.core.config import settings
from app.llm.runtime import ModelSettings
from app.models import OtelSpan, User

pytestmark = [pytest.mark.asyncio, pytest.mark.llm, pytest.mark.slow]


async def _run_conversation_turn(
    session: AsyncSession, test_user: User, model_settings: ModelSettings
) -> str:
    _, assistant_message = await handle_conversation_turn(
        conversation_id=None,
        parent_message_id=None,
        user_prompt="hi",
        is_regeneration=False,
        chatbot_model_settings=model_settings,
        guardrail_model_settings=model_settings,
        search_model_settings=model_settings,
        user_id=test_user.id,
        session=session,
        enable_guardrails=False,
    )

    assert assistant_message.conversation_id is not None
    return str(assistant_message.conversation_id)


@pytest.mark.asyncio
async def test_conversation_turn_creates_spans(session: AsyncSession, test_user: User) -> None:
    otel.configure_otel_span_processor()

    model_settings = ModelSettings(
        model=settings.CHATBOT_MODEL,
        temperature=settings.CHATBOT_MODEL_TEMPERATURE,
        max_tokens=settings.CHATBOT_MODEL_MAX_TOKENS,
    )

    conversation_id = await _run_conversation_turn(session, test_user, model_settings)

    await otel.wait_for_pending_spans()
    await session.flush()

    root_stmt = (
        select(OtelSpan)
        .where(OtelSpan.attributes["app.conversation_id"].astext == conversation_id)
        .order_by(OtelSpan.start_time)
    )
    result = await session.execute(root_stmt)
    root_spans = result.scalars().all()

    assert root_spans, "Expected OTEL spans for conversation turn"

    trace_ids = {span.trace_id for span in root_spans}
    trace_stmt = select(OtelSpan).where(OtelSpan.trace_id.in_(trace_ids))
    trace_result = await session.execute(trace_stmt)
    trace_spans = trace_result.scalars().all()

    span_names = {span.name for span in trace_spans}
    assert any("handle_conversation_turn" in name for name in span_names)
    assert any(name.startswith("chat ") for name in span_names)
