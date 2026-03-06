import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_user,
    get_request_user,
    require_user_roles,
)
from app.chat.engine import handle_conversation_turn
from app.chat.internal_summary import summarize_internal_conversation
from app.chat.title import (
    build_fallback_title,
    generate_conversation_title,
    generate_conversation_title_from_transcript,
    update_conversation_title,
)
from app.core.app_settings import get_guardrails_blocked_message
from app.core.authz import ensure_owner_or_roles
from app.core.config import settings
from app.core.db import get_session
from app.llm.runtime import ModelSettings
from app.models import Conversation, User, UserRole
from app.utils import logger

# Set to track background tasks and prevent them from being garbage collected
_background_tasks: set[asyncio.Task[Any]] = set()

router = APIRouter(tags=["messages"])


async def _persist_conversation_title(conversation_id: UUID, title: str) -> None:
    async with get_session() as session:
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            logger.warning(
                "Conversation not found while updating title",
                extra={"conversation_id": conversation_id},
            )
            return
        conversation.title = title


async def _generate_initial_title(
    conversation_id: UUID,
    user_prompt: str,
    *,
    is_internal: bool,
    on_title: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    title = await generate_conversation_title(
        user_prompt, conversation_id=conversation_id, is_internal=is_internal
    )
    await _persist_conversation_title(conversation_id, title)
    if on_title is not None:
        await on_title(title)


async def _generate_transcript_title(
    conversation_id: UUID,
    user_prompt: str,
    assistant_message: str,
    *,
    is_internal: bool,
    on_title: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    role_label = "Staff" if is_internal else "User"
    transcript = f"{role_label}: {user_prompt}\n\nAssistant: {assistant_message}"
    fallback = build_fallback_title(user_prompt)
    title = await generate_conversation_title_from_transcript(
        transcript, conversation_id=conversation_id, is_internal=is_internal, fallback=fallback
    )
    await _persist_conversation_title(conversation_id, title)
    if on_title is not None:
        await on_title(title)


def _format_sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


class ChatRequest(BaseModel):
    """Simplified chat request - only essential fields."""

    user_prompt: str
    conversation_id: UUID | None = None
    parent_message_id: UUID | None = None
    prompt_set_version_id: UUID | None = None
    chatbot_model: str | None = None
    search_model: str | None = None
    guardrail_model: str | None = None
    chatbot_reasoning_effort: str | None = None
    search_reasoning_effort: str | None = None
    guardrail_reasoning_effort: str | None = None
    is_regeneration: bool = False


class ChatResponse(BaseModel):
    """Simplified chat response - only essential fields."""

    conversation_id: UUID
    conversation_title: str | None
    user_message_id: UUID
    assistant_message_id: UUID
    assistant_message: str
    parent_message_id: UUID | None


def _normalize_reasoning_effort(value: str | None, *, label: str) -> str | None:
    if value is None or value == "":
        return None
    allowed = {"none", "low", "medium", "high", "xhigh"}
    if value not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid reasoning effort for {label}.")
    return value


def _get_model_settings(
    request: ChatRequest, *, allow_overrides: bool
) -> tuple[ModelSettings, ModelSettings, ModelSettings]:
    """Get model settings from server config with optional overrides."""
    has_override = any(
        value is not None and value != ""
        for value in (
            request.chatbot_model,
            request.search_model,
            request.guardrail_model,
            request.chatbot_reasoning_effort,
            request.search_reasoning_effort,
            request.guardrail_reasoning_effort,
        )
    )
    if has_override and not allow_overrides:
        raise HTTPException(status_code=403, detail="Model overrides are not allowed.")

    chatbot_model = (
        request.chatbot_model
        if allow_overrides and request.chatbot_model not in (None, "")
        else settings.CHATBOT_MODEL
    )
    guardrail_model = (
        request.guardrail_model
        if allow_overrides and request.guardrail_model not in (None, "")
        else settings.GUARDRAIL_MODEL
    )
    search_model = (
        request.search_model
        if allow_overrides and request.search_model not in (None, "")
        else settings.SEARCH_AGENT_MODEL
    )

    chatbot_reasoning_effort = (
        _normalize_reasoning_effort(request.chatbot_reasoning_effort, label="chatbot")
        if allow_overrides
        else None
    )
    search_reasoning_effort = (
        _normalize_reasoning_effort(request.search_reasoning_effort, label="search")
        if allow_overrides
        else None
    )
    guardrail_reasoning_effort = (
        _normalize_reasoning_effort(request.guardrail_reasoning_effort, label="guardrails")
        if allow_overrides
        else None
    )

    chatbot = ModelSettings(
        model=chatbot_model,
        temperature=settings.CHATBOT_MODEL_TEMPERATURE
        if settings.CHATBOT_MODEL_TEMPERATURE
        else None,
        max_tokens=settings.CHATBOT_MODEL_MAX_TOKENS if settings.CHATBOT_MODEL_MAX_TOKENS else None,
        openai_reasoning_effort=chatbot_reasoning_effort if "gpt-5" in chatbot_model else None,
    )
    guardrail = ModelSettings(
        model=guardrail_model,
        temperature=settings.GUARDRAIL_MODEL_TEMPERATURE
        if settings.GUARDRAIL_MODEL_TEMPERATURE
        else None,
        max_tokens=settings.GUARDRAIL_MODEL_MAX_TOKENS
        if settings.GUARDRAIL_MODEL_MAX_TOKENS
        else None,
        openai_reasoning_effort=guardrail_reasoning_effort if "gpt-5" in guardrail_model else None,
    )
    search = ModelSettings(
        model=search_model,
        temperature=settings.SEARCH_AGENT_MODEL_TEMPERATURE
        if settings.SEARCH_AGENT_MODEL_TEMPERATURE
        else None,
        max_tokens=settings.SEARCH_AGENT_MODEL_MAX_TOKENS
        if settings.SEARCH_AGENT_MODEL_MAX_TOKENS
        else None,
        openai_reasoning_effort=search_reasoning_effort if "gpt-5" in search_model else None,
    )
    return chatbot, guardrail, search


async def _handle_chat(
    request: ChatRequest, session: SessionDep, current_user: User | None, *, is_internal: bool
) -> ChatResponse:
    """Handle chat request and return response."""
    if is_internal:
        # Internal mode requires authentication
        if current_user is None or current_user.is_public_user():
            raise HTTPException(status_code=401, detail="Authentication required for internal mode")

        if request.conversation_id:
            conversation = await session.get(Conversation, request.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            ensure_owner_or_roles(conversation.user_id, current_user)

    chatbot_settings, guardrail_settings, search_settings = _get_model_settings(
        request, allow_overrides=is_internal
    )

    user_message_id, assistant_message_out = await handle_conversation_turn(
        conversation_id=request.conversation_id,
        parent_message_id=request.parent_message_id,
        user_prompt=request.user_prompt,
        chatbot_model_settings=chatbot_settings,
        guardrail_model_settings=guardrail_settings,
        search_model_settings=search_settings,
        is_regeneration=request.is_regeneration,
        is_internal=is_internal,
        enable_guardrails=settings.ENABLE_GUARDRAILS,
        max_guardrails_retries=settings.MAX_GUARDRAILS_RETRIES,
        user_id=current_user.id if is_internal and current_user else None,
        session=session,
        chatbot_version_id=request.prompt_set_version_id if is_internal else None,
    )

    # conversation_id is always set after a successful turn
    assert assistant_message_out.conversation_id is not None

    # Replace content with canned message if guardrails blocked the response
    assistant_message = (
        get_guardrails_blocked_message()
        if assistant_message_out.guardrails_blocked
        else assistant_message_out.content
    )

    conversation = await session.get(Conversation, assistant_message_out.conversation_id)
    conversation_title = conversation.title if conversation else None

    return ChatResponse(
        conversation_id=assistant_message_out.conversation_id,
        conversation_title=conversation_title,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_out.id,
        assistant_message=assistant_message,
        parent_message_id=assistant_message_out.parent_id,
    )


@router.post(
    "/messages/public",
    response_model=ChatResponse,
    dependencies=[Depends(require_user_roles(get_request_user, UserRole.PUBLIC))],
)
async def send_public_message(request: ChatRequest, session: SessionDep) -> Any:
    """Send a chat message from the public widget.

    Does not require authentication - public endpoint.
    Uses model settings from server configuration.
    """
    result = await _handle_chat(request, session, None, is_internal=False)
    await session.commit()

    if request.conversation_id is None:
        task = asyncio.create_task(
            update_conversation_title(
                result.conversation_id, request.user_prompt, is_internal=False
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return result


@router.post(
    "/messages/internal/stream",
    response_class=StreamingResponse,
    dependencies=[
        Depends(require_user_roles(get_current_user, UserRole.USER, UserRole.ADMIN, UserRole.DEV))
    ],
)
async def send_internal_message_stream(
    request: ChatRequest, session: SessionDep, current_user: CurrentUser
) -> StreamingResponse:
    """Stream a chat message response with async title and activity updates."""
    if current_user.is_public_user():
        raise HTTPException(status_code=401, detail="Authentication required for internal mode")

    if request.conversation_id:
        conversation = await session.get(Conversation, request.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        ensure_owner_or_roles(conversation.user_id, current_user)

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def emit(event: str, payload: dict[str, Any]) -> None:
        await queue.put(_format_sse_event(event, payload))

    async def worker() -> None:
        initial_title_task: asyncio.Task[None] | None = None
        transcript_title_task: asyncio.Task[None] | None = None

        try:
            chatbot_settings, guardrail_settings, search_settings = _get_model_settings(
                request, allow_overrides=True
            )
            conversation_id = request.conversation_id

            is_new_conversation = conversation_id is None

            if is_new_conversation:
                title = build_fallback_title(request.user_prompt)
                conversation = Conversation(title=title, user_id=current_user.id, is_public=False)
                session.add(conversation)
                await session.flush()
                conversation_id = conversation.id

                await emit(
                    "conversation",
                    {
                        "conversation_id": str(conversation_id),
                        "conversation_title": conversation.title,
                    },
                )
            else:
                await emit("conversation", {"conversation_id": str(conversation_id)})

            async def emit_title_update(title: str, stage: str) -> None:
                await emit(
                    "title_update",
                    {"conversation_id": str(conversation_id), "title": title, "stage": stage},
                )

            if is_new_conversation:
                initial_title_task = asyncio.create_task(
                    _generate_initial_title(
                        conversation_id,
                        request.user_prompt,
                        is_internal=True,
                        on_title=lambda title: emit_title_update(title, "initial"),
                    )
                )

            assert conversation_id is not None

            async def emit_agent_event(event: str, payload: dict[str, Any]) -> None:
                await emit(event, {"conversation_id": str(conversation_id), **payload})

            user_message_id, assistant_message_out = await handle_conversation_turn(
                conversation_id=conversation_id,
                parent_message_id=request.parent_message_id,
                user_prompt=request.user_prompt,
                chatbot_model_settings=chatbot_settings,
                guardrail_model_settings=guardrail_settings,
                search_model_settings=search_settings,
                is_regeneration=request.is_regeneration,
                is_internal=True,
                enable_guardrails=settings.ENABLE_GUARDRAILS,
                max_guardrails_retries=settings.MAX_GUARDRAILS_RETRIES,
                user_id=current_user.id,
                session=session,
                event_emitter=emit_agent_event,
                chatbot_version_id=request.prompt_set_version_id,
            )

            assistant_message = (
                get_guardrails_blocked_message()
                if assistant_message_out.guardrails_blocked
                else assistant_message_out.content
            )

            await session.commit()

            await emit(
                "assistant_message",
                {
                    "conversation_id": str(conversation_id),
                    "user_message_id": str(user_message_id),
                    "assistant_message_id": str(assistant_message_out.id),
                    "assistant_message": assistant_message,
                    "parent_message_id": (
                        str(assistant_message_out.parent_id)
                        if assistant_message_out.parent_id is not None
                        else None
                    ),
                },
            )

            summary_task = asyncio.create_task(summarize_internal_conversation(conversation_id))
            _background_tasks.add(summary_task)
            summary_task.add_done_callback(_background_tasks.discard)

            if is_new_conversation:
                transcript_title_task = asyncio.create_task(
                    _generate_transcript_title(
                        conversation_id,
                        request.user_prompt,
                        assistant_message,
                        is_internal=True,
                        on_title=lambda title: emit_title_update(title, "post_assistant"),
                    )
                )

            if initial_title_task is not None:
                await initial_title_task
            if transcript_title_task is not None:
                await transcript_title_task
        except Exception as exc:
            logger.exception("Failed to stream chat response")
            await emit("error", {"message": str(exc)})
        finally:
            await queue.put(None)

    worker_task = asyncio.create_task(worker())

    async def event_stream() -> AsyncIterator[str]:
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            if not worker_task.done():
                worker_task.cancel()
            await worker_task

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
