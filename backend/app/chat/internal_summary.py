import logging
from uuid import UUID

from sqlalchemy import select

from app.chat.transcripts import format_transcript
from app.chat.tree_utils import get_current_branch_path
from app.core.config import settings
from app.core.db import get_session
from app.llm.agents.summary import create_summary_agent, render_summary_prompt
from app.llm.runtime import run_agent_with_span
from app.models import Conversation, Message

logger = logging.getLogger(__name__)


async def _get_active_transcript(conversation_id: UUID) -> str | None:
    async with get_session() as session:
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            logger.warning(
                "Conversation not found while building internal summary",
                extra={"conversation_id": str(conversation_id)},
            )
            return None
        # Skip summary for public conversations
        if conversation.is_public:
            logger.debug(
                "Skipping summary generation for public conversation",
                extra={"conversation_id": str(conversation_id)},
            )
            return None

        message_path = await get_current_branch_path(session, conversation_id)
        if not message_path:
            logger.debug(
                "No messages found for internal conversation; skipping summary",
                extra={"conversation_id": str(conversation_id)},
            )
            return None

        stmt = select(Message).where(Message.id.in_(message_path))
        result = await session.execute(stmt)
        messages = list(result.scalars().all())

        messages_by_id = {message.id: message for message in messages}
        ordered_messages = [
            messages_by_id[msg_id] for msg_id in message_path if msg_id in messages_by_id
        ]

        if not ordered_messages:
            logger.debug(
                "Could not resolve ordered messages for summary",
                extra={"conversation_id": str(conversation_id)},
            )
            return None

        return format_transcript(ordered_messages, user_label="Staff")


async def _generate_internal_summary(transcript: str, *, conversation_id: str | None = None) -> str:
    prompt = await render_summary_prompt(transcript, is_internal=True)

    agent = create_summary_agent(settings.SUMMARIZER_MODEL, name="internal_summary")
    result = await run_agent_with_span(
        agent,
        prompt=prompt,
        span_name="summarize_internal_conversation",
        agent_name="internal_summary",
        is_internal=True,
        conversation_id=conversation_id,
    )

    return result.output


async def summarize_internal_conversation(conversation_id: UUID) -> None:
    """Generate and persist a summary for an internal conversation without blocking the request."""
    try:
        transcript = await _get_active_transcript(conversation_id)
        if not transcript:
            return

        summary = await _generate_internal_summary(transcript, conversation_id=str(conversation_id))

        async with get_session() as session:
            conversation = await session.get(Conversation, conversation_id)
            if not conversation:
                logger.warning(
                    "Conversation disappeared before saving summary",
                    extra={"conversation_id": str(conversation_id)},
                )
                return

            conversation.summary = summary
    except Exception:
        logger.exception(
            "Failed to generate or save internal conversation summary",
            extra={"conversation_id": str(conversation_id)},
        )
