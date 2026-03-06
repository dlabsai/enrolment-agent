import logging
from uuid import UUID

from app.core.config import settings
from app.core.db import get_session
from app.llm.agents.title import (
    create_title_agent,
    render_title_prompt,
    render_title_transcript_prompt,
)
from app.llm.runtime import run_agent_with_span
from app.models import Conversation

logger = logging.getLogger(__name__)

_TITLE_MAX_LENGTH = 60


def build_fallback_title(user_prompt: str) -> str:
    trimmed = user_prompt.strip()
    if len(trimmed) <= _TITLE_MAX_LENGTH:
        return trimmed
    return f"{trimmed[:_TITLE_MAX_LENGTH].rstrip()}..."


def _normalize_title(title: str, fallback: str) -> str:
    normalized = title.strip()
    for char in ('"', "'", "“", "”", "`"):
        normalized = normalized.strip(char)
    if not normalized:
        return fallback

    first_line = normalized.splitlines()[0].strip()
    if not first_line:
        return fallback

    first_line = first_line.rstrip(".!?")
    if len(first_line) <= _TITLE_MAX_LENGTH:
        return first_line

    return f"{first_line[:_TITLE_MAX_LENGTH].rstrip()}..."


async def generate_conversation_title(
    user_prompt: str, *, conversation_id: UUID | None = None, is_internal: bool = False
) -> str:
    fallback = build_fallback_title(user_prompt)

    prompt = await render_title_prompt(user_prompt, is_internal=is_internal)

    try:
        agent = create_title_agent(settings.SUMMARIZER_MODEL)
        result = await run_agent_with_span(
            agent,
            prompt=prompt,
            span_name="generate_conversation_title",
            agent_name="conversation_title",
            is_internal=is_internal,
            conversation_id=str(conversation_id) if conversation_id is not None else None,
        )

        return _normalize_title(result.output, fallback)
    except Exception:
        logger.exception("Error generating conversation title")
        return fallback


async def generate_conversation_title_from_transcript(
    transcript: str,
    *,
    conversation_id: UUID | None = None,
    is_internal: bool = False,
    fallback: str,
) -> str:
    normalized_transcript = transcript.strip()
    if not normalized_transcript:
        return fallback

    prompt = await render_title_transcript_prompt(normalized_transcript, is_internal=is_internal)

    try:
        agent = create_title_agent(settings.SUMMARIZER_MODEL)
        result = await run_agent_with_span(
            agent,
            prompt=prompt,
            span_name="generate_conversation_title_from_transcript",
            agent_name="conversation_title",
            is_internal=is_internal,
            conversation_id=str(conversation_id) if conversation_id is not None else None,
        )

        return _normalize_title(result.output, fallback)
    except Exception:
        logger.exception("Error generating conversation title from transcript")
        return fallback


async def update_conversation_title(
    conversation_id: UUID, user_prompt: str, *, is_internal: bool
) -> None:
    try:
        title = await generate_conversation_title(
            user_prompt, conversation_id=conversation_id, is_internal=is_internal
        )

        async with get_session() as session:
            conversation = await session.get(Conversation, conversation_id)
            if not conversation:
                logger.warning(
                    "Conversation not found while updating title",
                    extra={"conversation_id": conversation_id},
                )
                return

            conversation.title = title
    except Exception:
        logger.exception(
            "Failed to update conversation title", extra={"conversation_id": conversation_id}
        )
