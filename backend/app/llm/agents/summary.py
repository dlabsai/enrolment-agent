from pydantic_ai import Agent

from app.llm.prompts import get_jinja_environment_for_scope, get_template_context
from app.llm.providers import get_instrumentation_settings, get_pydantic_ai_model
from app.models import ChatbotVersionScope


def create_summary_agent(model: str, *, name: str = "conversation_summary") -> Agent[None, str]:
    return Agent(
        get_pydantic_ai_model(model),
        output_type=str,
        instrument=get_instrumentation_settings(),
        name=name,
    )


async def render_summary_prompt(transcript: str, *, is_internal: bool) -> str:
    env = await get_jinja_environment_for_scope(
        scope=ChatbotVersionScope.SUMMARY, is_internal=is_internal
    )
    template = env.get_template("summary_agent.j2")
    return template.render(transcript=transcript, **get_template_context())
