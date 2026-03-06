from typing import Protocol


class SpanLike(Protocol):
    def set_attribute(self, key: str, value: object) -> None: ...


def set_agent_span_attributes(
    span: SpanLike, *, agent_name: str, is_internal: bool, conversation_id: str | None = None
) -> None:
    """Apply shared logfire span attributes for agent runs."""
    is_ai = True
    span.set_attribute("app.is_ai", is_ai)
    span.set_attribute("gen_ai.agent.name", agent_name)
    span.set_attribute("app.is_internal", is_internal)
    if conversation_id is not None:
        span.set_attribute("app.conversation_id", conversation_id)
