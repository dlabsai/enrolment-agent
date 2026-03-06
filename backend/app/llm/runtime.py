import time
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import logfire
from pydantic_ai import Agent, AgentRunResult, AgentStreamEvent, RunContext
from pydantic_ai.settings import ModelSettings as PydanticModelSettings

from app.llm.telemetry import set_agent_span_attributes


@dataclass
class ModelSettings:
    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    openai_reasoning_summary: str | None = None
    openai_reasoning_effort: str | None = None

    def to_pydantic_settings(self) -> PydanticModelSettings:
        """Convert to PydanticAI ModelSettings."""
        settings: dict[str, Any] = {}

        if self.max_tokens is not None and self.max_tokens > 0:
            settings["max_tokens"] = self.max_tokens

        model_name = self.model.lower()
        supports_temperature = "gpt-5" not in model_name and "gpt-oss" not in model_name
        if supports_temperature and self.temperature is not None:
            settings["temperature"] = self.temperature
        elif supports_temperature and self.temperature is None:
            settings["temperature"] = 0.0

        reasoning_summary = self.openai_reasoning_summary
        if reasoning_summary is None and "gpt-5" in model_name:
            reasoning_summary = "detailed"
        if reasoning_summary is not None:
            settings["openai_reasoning_summary"] = reasoning_summary

        reasoning_effort = self.openai_reasoning_effort
        if reasoning_effort is None and "gpt-5" in model_name:
            reasoning_effort = "medium"
        if reasoning_effort is not None:
            settings["openai_reasoning_effort"] = reasoning_effort

        return PydanticModelSettings(**settings)


async def run_agent[D, T](
    agent: Agent[D, T],
    prompt: str,
    model_settings: ModelSettings,
    *,
    deps: D | None = None,
    metadata: dict[str, Any] | None = None,
    event_handler: Callable[[AgentStreamEvent], Awaitable[None]] | None = None,
) -> tuple[AgentRunResult[T], float]:
    """Run an agent with standard boilerplate for timing and tracing.

    Returns:
        Tuple of (result, duration)

    """
    pydantic_settings = model_settings.to_pydantic_settings()

    span_name = f"chat {model_settings.model}"

    event_stream_handler: (
        Callable[[RunContext[D], AsyncIterable[AgentStreamEvent]], Awaitable[None]] | None
    ) = None
    if event_handler is not None:

        async def handle_event_stream(
            _ctx: RunContext[D], event_stream: AsyncIterable[AgentStreamEvent]
        ) -> None:
            async for event in event_stream:
                await event_handler(event)

        event_stream_handler = handle_event_stream

    start_time = time.time()
    with logfire.span(span_name) as span:
        is_ai = True
        span.set_attribute("app.is_ai", is_ai)

        if metadata is not None:
            conversation_id = metadata.get("conversation_id")
            if conversation_id is not None:
                span.set_attribute("app.conversation_id", conversation_id)
            if "conversation_turn" in metadata:
                span.set_attribute("app.conversation_turn", metadata["conversation_turn"])
            if "is_internal" in metadata:
                span.set_attribute("app.is_internal", metadata["is_internal"])
            if "user_id" in metadata:
                span.set_attribute("app.user_id", metadata["user_id"])

        if deps is not None:
            if event_stream_handler is None:
                result = await agent.run(
                    prompt, deps=deps, model_settings=pydantic_settings, metadata=metadata
                )
            else:
                result = await agent.run(
                    prompt,
                    deps=deps,
                    model_settings=pydantic_settings,
                    metadata=metadata,
                    event_stream_handler=event_stream_handler,
                )
        elif event_stream_handler is None:
            result = await agent.run(
                prompt,
                deps=deps,  # type: ignore[arg-type]
                model_settings=pydantic_settings,
                metadata=metadata,
            )
        else:
            result = await agent.run(
                prompt,
                deps=deps,  # type: ignore[arg-type]
                model_settings=pydantic_settings,
                metadata=metadata,
                event_stream_handler=event_stream_handler,
            )

    duration = time.time() - start_time

    return result, duration


async def run_agent_with_span[D, T](
    agent: Agent[D, T],
    *,
    prompt: str,
    span_name: str,
    agent_name: str,
    is_internal: bool,
    conversation_id: str | None = None,
    deps: D | None = None,
) -> AgentRunResult[T]:
    """Run an agent inside a logfire span with standard attributes."""
    with logfire.span(span_name) as span:
        set_agent_span_attributes(
            span, agent_name=agent_name, is_internal=is_internal, conversation_id=conversation_id
        )
        return await agent.run(prompt, deps=deps)  # type: ignore[arg-type]
