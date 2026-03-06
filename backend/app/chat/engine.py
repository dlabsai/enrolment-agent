import copy
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import logfire
from devtools import debug
from fastapi.encoders import jsonable_encoder
from jinja2 import Template
from pydantic_ai import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    RetryPromptPart,
    ThinkingPart,
    ThinkingPartDelta,
    ToolReturnPart,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.config import DEBUG
from app.chat.engine_utils import (
    MessageDict,
    get_assistant_message_content,
    get_current_date_gmt_minus_4,
)
from app.chat.title import build_fallback_title
from app.chat.tools import Deps, get_deps, get_deps_with_db_templates
from app.chat.tree_utils import get_conversation_path
from app.llm.agents.chatbot import create_chatbot_agent, render_chatbot_prompt
from app.llm.agents.guardrails import GuardrailsDeps, create_guardrails_agent
from app.llm.agents.search import create_search_agent
from app.llm.prompts import get_deployed_templates, get_templates_for_version
from app.llm.runtime import ModelSettings, run_agent
from app.models import ChatbotVersionScope, Conversation, Message, Rating


@dataclass
class Feedback:
    id: UUID
    rating: Rating
    user_id: UUID
    user_name: str
    is_current_user: bool
    created_at: datetime
    updated_at: datetime
    text: str | None = None


def _default_feedback() -> list[Feedback]:
    return []


@dataclass
class MessageOut:
    id: UUID
    role: str
    content: str
    created_at: datetime
    parent_id: UUID | None
    conversation_id: UUID | None = None
    guardrails_blocked: bool = False
    feedback: list[Feedback] = field(default_factory=_default_feedback)


EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]
SystemPromptEmitter = Callable[[str, int | None], None]


async def _emit_agent_stage(
    event_emitter: EventEmitter | None,
    *,
    stage: str,
    status: str,
    duration: float | None = None,
    iteration: int | None = None,
) -> None:
    if event_emitter is None:
        return

    payload: dict[str, Any] = {"stage": stage, "status": status}
    if duration is not None:
        payload["duration_ms"] = int(duration * 1000)
    if iteration is not None:
        payload["iteration"] = iteration

    await event_emitter("agent_stage", payload)


def _serialize_tool_args(args: str | dict[str, Any] | None) -> Any | None:
    if args is None:
        return None
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return jsonable_encoder(args)


def _serialize_tool_output(output: Any) -> Any:
    return jsonable_encoder(output)


def _serialize_error_text(error: Any) -> str:
    if isinstance(error, str):
        return error
    try:
        return json.dumps(jsonable_encoder(error), indent=2)
    except TypeError:
        return str(error)


def _create_tool_event_handler(
    event_emitter: EventEmitter | None, *, stage: str, iteration: int | None = None
) -> Callable[[AgentStreamEvent], Awaitable[None]] | None:
    if event_emitter is None:
        return None

    tool_lookup: dict[str, str] = {}
    thinking_content: dict[int, str] = {}
    thinking_ids: dict[int, str] = {}

    async def handle_event(event: AgentStreamEvent) -> None:
        if isinstance(event, FunctionToolCallEvent):
            tool_call_id = event.tool_call_id
            tool_name = event.part.tool_name
            tool_lookup[tool_call_id] = tool_name

            payload: dict[str, Any] = {
                "stage": stage,
                "status": "start",
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
            }
            tool_input = _serialize_tool_args(event.part.args)
            if tool_input is not None:
                payload["tool_input"] = tool_input
            if iteration is not None:
                payload["iteration"] = iteration

            await event_emitter("tool_call", payload)
            return

        if isinstance(event, FunctionToolResultEvent):
            tool_call_id = event.tool_call_id
            tool_name = tool_lookup.get(tool_call_id)
            status = "end"
            tool_output: Any | None = None
            tool_error_text: str | None = None

            if isinstance(event.result, RetryPromptPart):
                status = "error"
                tool_error_text = _serialize_error_text(event.result.content)
                if event.result.tool_name is not None:
                    tool_name = event.result.tool_name
            elif isinstance(event.result, ToolReturnPart):
                tool_output = _serialize_tool_output(event.result.content)
                tool_name = event.result.tool_name

            payload: dict[str, Any] = {
                "stage": stage,
                "status": status,
                "tool_call_id": tool_call_id,
            }
            if tool_name is not None:
                payload["tool_name"] = tool_name
            if tool_output is not None:
                payload["tool_output"] = tool_output
            if tool_error_text is not None:
                payload["tool_error_text"] = tool_error_text
            if iteration is not None:
                payload["iteration"] = iteration

            await event_emitter("tool_call", payload)
            return

        if isinstance(event, PartStartEvent) and isinstance(event.part, ThinkingPart):
            thinking_id = event.part.id or f"{stage}:{iteration or 0}:{event.index}"
            thinking_ids[event.index] = thinking_id
            thinking_content[event.index] = event.part.content
            payload: dict[str, Any] = {
                "stage": stage,
                "status": "start",
                "thinking_id": thinking_id,
            }
            if event.part.content:
                payload["content"] = event.part.content
            if iteration is not None:
                payload["iteration"] = iteration
            await event_emitter("thinking", payload)
            return

        if isinstance(event, PartDeltaEvent) and isinstance(event.delta, ThinkingPartDelta):
            thinking_id = thinking_ids.get(event.index) or f"{stage}:{iteration or 0}:{event.index}"
            thinking_ids[event.index] = thinking_id
            current = thinking_content.get(event.index, "")
            if event.delta.content_delta:
                current += event.delta.content_delta
                thinking_content[event.index] = current
            payload: dict[str, Any] = {
                "stage": stage,
                "status": "delta",
                "thinking_id": thinking_id,
            }
            if current:
                payload["content"] = current
            if iteration is not None:
                payload["iteration"] = iteration
            await event_emitter("thinking", payload)
            return

        if isinstance(event, PartEndEvent) and isinstance(event.part, ThinkingPart):
            thinking_id = (
                thinking_ids.get(event.index)
                or event.part.id
                or f"{stage}:{iteration or 0}:{event.index}"
            )
            thinking_ids[event.index] = thinking_id
            thinking_content[event.index] = event.part.content
            payload = {
                "stage": stage,
                "status": "end",
                "thinking_id": thinking_id,
                "content": event.part.content,
            }
            if iteration is not None:
                payload["iteration"] = iteration
            await event_emitter("thinking", payload)
            return

    return handle_event


def _get_transcript(messages: list[MessageDict], limit_to_n_last: int | None = None) -> str:
    recent_messages = messages[-limit_to_n_last:] if limit_to_n_last is not None else messages
    formatted_messages: list[str] = []
    for message in recent_messages:
        role_display = "User" if message["role"] == "user" else "Assistant"
        formatted_messages.append(f"{role_display}: {message['content']}")

    return "\n\n".join(formatted_messages)


async def _run_guardrails(
    guardrail_model_settings: ModelSettings,
    guardrails_log: list[dict[str, str]],
    response: str,
    *,
    is_internal: bool = False,
    db_templates: dict[str, str] | None = None,
    trace_metadata: dict[str, Any] | None = None,
    event_emitter: EventEmitter | None = None,
    iteration: int | None = None,
) -> tuple[bool, str, list[dict[str, str]], float]:
    """Run guardrails check using PydanticAI Agent.

    Returns:
        Tuple of (is_valid, feedback_message, guardrails_log, duration)
    """
    guardrails_log = copy.deepcopy(guardrails_log)

    agent = create_guardrails_agent(
        guardrail_model_settings.model, is_internal=is_internal, db_templates=db_templates
    )
    deps = GuardrailsDeps(response_to_check=response)

    await _emit_agent_stage(event_emitter, stage="guardrails", status="start", iteration=iteration)

    result, duration = await run_agent(
        agent,
        "Check the chatbot message.",
        guardrail_model_settings,
        deps=deps,
        metadata=trace_metadata,
    )

    await _emit_agent_stage(
        event_emitter, stage="guardrails", status="end", duration=duration, iteration=iteration
    )

    guardrails_result = result.output

    if DEBUG:
        print("\nGuardrails result:")
        debug(guardrails_result)

    guardrails_feedback_ok = guardrails_result.is_valid
    guardrails_feedback_message = guardrails_result.feedback or ""

    if not guardrails_feedback_ok:
        guardrails_log.append(
            {"assistant_message": response, "guardrails_message": guardrails_feedback_message}
        )

    return guardrails_feedback_ok, guardrails_feedback_message, guardrails_log, duration


async def _execute_search_agent(
    messages: list[MessageDict],
    model_settings: ModelSettings,
    deps: Deps,
    *,
    trace_metadata: dict[str, Any] | None = None,
    event_emitter: EventEmitter | None = None,
    iteration: int | None = None,
) -> tuple[str, float]:
    """Execute search agent using PydanticAI Agent.

    Returns:
        Tuple of (search_content, duration)
    """
    agent = create_search_agent(model_settings.model, deps)

    # Convert messages to user prompt (search agent gets conversation history)
    transcript = _get_transcript(messages)

    await _emit_agent_stage(event_emitter, stage="search", status="start", iteration=iteration)

    tool_event_handler = _create_tool_event_handler(
        event_emitter, stage="search", iteration=iteration
    )

    result, duration = await run_agent(
        agent,
        transcript,
        model_settings,
        deps=deps,
        metadata=trace_metadata,
        event_handler=tool_event_handler,
    )

    await _emit_agent_stage(
        event_emitter, stage="search", status="end", duration=duration, iteration=iteration
    )

    return result.output, duration


# TODO: rename
async def _handle_one_chatbot_guardrails_iteration(
    *,
    main_template: Template,
    branch_messages: list[MessageDict],
    chatbot_model_settings: ModelSettings,
    search_model_settings: ModelSettings,
    guardrail_model_settings: ModelSettings,
    deps: Deps,
    guardrails_feedback_ok: bool,
    guardrails_feedback_message: str,
    guardrails_log: list[dict[str, str]],
    enable_guardrails: bool = True,
    trace_metadata: dict[str, Any] | None = None,
    event_emitter: EventEmitter | None = None,
    system_prompt_emitter: SystemPromptEmitter | None = None,
    iteration: int | None = None,
) -> tuple[
    MessageDict,
    bool,
    str,
    list[dict[str, Any]],
    float | None,  # search_time
    float | None,  # guardrail_time
    float,  # chatbot_duration
]:
    search_time: float | None = None
    guardrail_time: float | None = None

    # Use search agent to gather information first
    search_content, search_time = await _execute_search_agent(
        messages=branch_messages,
        model_settings=search_model_settings,
        deps=deps,
        trace_metadata=trace_metadata,
        event_emitter=event_emitter,
        iteration=iteration,
    )

    main_system_prompt = render_chatbot_prompt(
        main_template,
        current_date=get_current_date_gmt_minus_4(),
        guardrails_agent_response=guardrails_feedback_message,
        search_agent_response=search_content,
    )

    if system_prompt_emitter is not None:
        system_prompt_emitter(main_system_prompt, iteration)

    # Create and run the chatbot agent using PydanticAI
    chatbot_agent = create_chatbot_agent(chatbot_model_settings.model, None, main_system_prompt)

    # Build user prompt from conversation history
    transcript = _get_transcript(branch_messages)

    await _emit_agent_stage(event_emitter, stage="chatbot", status="start", iteration=iteration)

    tool_event_handler = _create_tool_event_handler(
        event_emitter, stage="chatbot", iteration=iteration
    )

    result, chatbot_duration = await run_agent(
        chatbot_agent,
        transcript,
        chatbot_model_settings,
        deps=deps,
        metadata=trace_metadata,
        event_handler=tool_event_handler,
    )

    await _emit_agent_stage(
        event_emitter, stage="chatbot", status="end", duration=chatbot_duration, iteration=iteration
    )

    response = result.output
    if DEBUG:
        debug(response)

    guardrails_log = copy.deepcopy(guardrails_log)

    # Build assistant message dict for compatibility
    assistant_message: MessageDict = {"role": "assistant", "content": response, "tool_calls": None}

    if enable_guardrails:
        (
            guardrails_feedback_ok,
            guardrails_feedback_message,
            guardrails_log,
            guardrail_time,
        ) = await _run_guardrails(
            guardrail_model_settings,
            guardrails_log,
            response,
            is_internal=deps.is_internal,
            db_templates=deps.db_templates if deps.db_templates else None,
            trace_metadata=trace_metadata,
            event_emitter=event_emitter,
            iteration=iteration,
        )
    else:
        guardrails_feedback_ok, guardrails_feedback_message = True, ""

    return (
        assistant_message,
        guardrails_feedback_ok,
        guardrails_feedback_message,
        guardrails_log,
        search_time,
        guardrail_time,
        chatbot_duration,
    )


def _build_trace_metadata(
    *, conversation_id: UUID | None, user_id: UUID | None, is_internal: bool, conversation_turn: int
) -> dict[str, Any] | None:
    metadata: dict[str, Any] = {"is_internal": is_internal, "conversation_turn": conversation_turn}
    if conversation_id is not None:
        metadata["conversation_id"] = str(conversation_id)
    if user_id is not None:
        metadata["user_id"] = str(user_id)
    return metadata or None


def _set_current_span_attributes(attributes: dict[str, Any]) -> None:
    with logfire.span("conversation_turn_attributes") as span:
        for key, value in attributes.items():
            if value is None:
                continue
            span.set_attribute(key, value)


@logfire.instrument()
async def handle_conversation_turn(
    *,
    conversation_id: UUID | None = None,
    parent_message_id: UUID | None = None,
    user_prompt: str,
    is_regeneration: bool = False,
    chatbot_model_settings: ModelSettings,
    guardrail_model_settings: ModelSettings,
    user_id: UUID | None,
    session: AsyncSession,
    search_model_settings: ModelSettings,
    is_internal: bool = False,
    enable_guardrails: bool = True,
    max_guardrails_retries: int = 2,
    chatbot_version_id: UUID | None = None,
    use_disk_templates: bool = False,
    event_emitter: EventEmitter | None = None,
    system_prompt_emitter: SystemPromptEmitter | None = None,
) -> tuple[UUID, MessageOut]:
    """Handle a conversation turn for a given project and template using tree structure.

    Parameters
    ----------
    - conversation_id=None, parent_message_id=None: Start new conversation
    - conversation_id=existing_id, parent_message_id=None: Continue at current branch leaf
    - conversation_id=existing_id, parent_message_id=specific_id: Create branch from specific
        message
    - chatbot_version_id: Optional specific prompt set version to use for testing.
        If None, uses deployed version (if any) or disk templates.
    - use_disk_templates: If True, always use disk templates (ignores deployed version).

    The system prompt message is generated dynamically at each turn based on the state.
    The state consists of extracted variables (set by LLM) and system variables (set by code).
    The user/assistant messages and the state are stored in the database as a tree.

    """
    start_timestamp = time.perf_counter()

    conversation_turn = 1
    branch_messages: list[dict[str, str]] = []
    parent_message: Message | None = None

    if not search_model_settings.model:
        raise ValueError("search_model_settings.model is required")

    if DEBUG:
        print("User message:")
        debug(user_prompt)

    if conversation_id is None:
        title = build_fallback_title(user_prompt)
        conversation = Conversation(title=title, user_id=user_id, is_public=not is_internal)
        session.add(conversation)
        await session.flush()
        conversation_id = conversation.id
    elif parent_message_id is None:
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError(f"Conversation with ID {conversation_id} not found")
    else:
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            raise ValueError(f"Conversation with ID {conversation_id} not found")

        parent_message = await session.get(Message, parent_message_id)
        if not parent_message:
            raise ValueError(f"Parent message with ID {parent_message_id} not found")

        branch_db_messages = await get_conversation_path(session, parent_message_id)
        branch_messages = [{"role": m.role, "content": m.content} for m in branch_db_messages]

        conversation_turn = (
            sum(1 for message in branch_db_messages if message.role == "assistant") + 1
        )

    if not is_regeneration:
        branch_messages.append({"role": "user", "content": user_prompt})

    trace_metadata = _build_trace_metadata(
        conversation_id=conversation_id,
        user_id=user_id,
        is_internal=is_internal,
        conversation_turn=conversation_turn,
    )
    _set_current_span_attributes(
        {
            "app.user_id": str(user_id) if user_id is not None else None,
            "app.is_internal": is_internal,
            "app.conversation_id": str(conversation_id),
            "app.conversation_turn": conversation_turn,
        }
    )

    # Add user message to chat history
    # Loop:
    #   Run chatbot with the main template
    #   Loop (when tool calls are present):
    #       Run tool calls
    #       Exit loop when normal chatbot response is received
    #   Run guardrails
    #   Exit loop if guardrails feedback is ok or max feedback loops reached
    # Add last assistant message to chat history

    assistant_message = None

    guardrails_feedback_ok = False
    guardrails_feedback_message = ""
    guardrail_retry_count = 0
    guardrails_log: list[dict[str, str]] = []

    # Get templates - either from specific version, deployed version, or disk
    db_templates: dict[str, str] = {}
    if chatbot_version_id:
        # Use specific version for testing (admin feature)
        db_templates = await get_templates_for_version(chatbot_version_id)
    elif not use_disk_templates:
        # Use deployed version if any, otherwise disk templates
        db_templates = await get_deployed_templates(
            is_internal=is_internal, scope=ChatbotVersionScope.ASSISTANT
        )
    # else: use_disk_templates=True, so db_templates stays empty -> disk templates

    if db_templates:
        deps = get_deps_with_db_templates(
            is_internal=is_internal,
            db_templates=db_templates,
            chatbot_version_id=chatbot_version_id,
        )
    else:
        deps = get_deps(is_internal=is_internal)

    main_template = deps.jinja_env.get_template("chatbot_agent.j2")

    search_time: float | None = None
    guardrail_time: float | None = None
    total_guardrail_time: float = 0.0
    chatbot_times: list[float] = []
    guardrail_times: list[float] = []

    while not guardrails_feedback_ok:
        if guardrail_retry_count > max_guardrails_retries:
            break

        (
            assistant_message,
            guardrails_feedback_ok,
            guardrails_feedback_message,
            guardrails_log,
            iteration_search_time,
            iteration_guardrail_time,
            iteration_chatbot_time,
        ) = await _handle_one_chatbot_guardrails_iteration(
            main_template=main_template,
            branch_messages=branch_messages,
            chatbot_model_settings=chatbot_model_settings,
            search_model_settings=search_model_settings,
            guardrail_model_settings=guardrail_model_settings,
            deps=deps,
            guardrails_feedback_ok=guardrails_feedback_ok,
            guardrails_feedback_message=guardrails_feedback_message,
            guardrails_log=guardrails_log,
            enable_guardrails=enable_guardrails,
            trace_metadata=trace_metadata,
            event_emitter=event_emitter,
            system_prompt_emitter=system_prompt_emitter,
            iteration=guardrail_retry_count + 1,
        )

        # Track per-iteration timing
        chatbot_times.append(iteration_chatbot_time)

        # Capture timing from first iteration (search only runs once)
        if search_time is None and iteration_search_time is not None:
            search_time = iteration_search_time

        # Accumulate guardrail time across retries
        if iteration_guardrail_time is not None:
            total_guardrail_time += iteration_guardrail_time
            guardrail_times.append(iteration_guardrail_time)

        if not guardrails_feedback_ok:
            guardrail_retry_count += 1

    # Set final guardrail time (None if guardrails weren't run)
    if total_guardrail_time > 0:
        guardrail_time = total_guardrail_time

    assert assistant_message

    # Track if guardrails blocked the response after max retries
    guardrails_blocked = not guardrails_feedback_ok

    response = get_assistant_message_content(assistant_message)

    branch_messages.append({"role": "assistant", "content": response})

    if is_regeneration:
        if not parent_message:
            raise ValueError("Parent message required for regeneration")

        assistant_db_message = Message(
            role="assistant",
            content=response,
            conversation=conversation,
            parent_id=parent_message.id,
            guardrails_blocked=guardrails_blocked,
        )
        session.add(assistant_db_message)
        await session.flush()
        parent_message.active_child = assistant_db_message

        user_message_id = parent_message.id
    else:
        user_db_message = Message(
            role="user",
            content=user_prompt,
            conversation=conversation,
            parent_id=parent_message.id if parent_message else None,
        )
        session.add(user_db_message)
        await session.flush()

        assistant_db_message = Message(
            role="assistant",
            content=response,
            conversation=conversation,
            parent_id=user_db_message.id,
            guardrails_blocked=guardrails_blocked,
        )
        session.add(assistant_db_message)
        await session.flush()

        user_db_message.active_child = assistant_db_message
        if user_db_message.parent:
            # for user message edit
            # TODO: Configure model to allow setting active_child directly.
            #   Now it would result in circular dependency error
            user_db_message.parent.active_child_id = user_db_message.id

        user_message_id = user_db_message.id

    assistant_message_id = assistant_db_message.id

    end_timestamp = time.perf_counter()
    total_time = end_timestamp - start_timestamp

    _set_current_span_attributes(
        {
            "app.conversation_id": str(conversation.id),
            "app.message_id": str(assistant_message_id),
            "app.conversation_turn": conversation_turn,
            "app.guardrails_blocked": guardrails_blocked,
            "app.guardrail_retries": guardrail_retry_count,
            "app.total_time": total_time,
            "app.search_time": search_time,
            "app.guardrail_time": guardrail_time,
            "app.chatbot_times": chatbot_times if len(chatbot_times) > 1 else None,
            "app.guardrail_times": guardrail_times if len(guardrail_times) > 1 else None,
        }
    )

    await session.refresh(conversation)
    await session.refresh(assistant_db_message)

    return (
        user_message_id,
        MessageOut(
            id=assistant_message_id,
            parent_id=assistant_db_message.parent_id,
            conversation_id=conversation.id,
            role=assistant_db_message.role,
            content=assistant_db_message.content,
            created_at=assistant_db_message.created_at,
            guardrails_blocked=assistant_db_message.guardrails_blocked,
        ),
    )
