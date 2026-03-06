from pydantic_ai import Agent

from app.llm.prompts import get_jinja_environment_for_scope, get_template_context
from app.llm.providers import get_instrumentation_settings, get_pydantic_ai_model
from app.models import ChatbotVersionScope


def create_title_agent(model: str, *, name: str = "conversation_title") -> Agent[None, str]:
    return Agent(
        get_pydantic_ai_model(model),
        output_type=str,
        instrument=get_instrumentation_settings(),
        name=name,
    )


async def render_title_prompt(user_prompt: str, *, is_internal: bool) -> str:
    env = await get_jinja_environment_for_scope(
        scope=ChatbotVersionScope.TITLE, is_internal=is_internal
    )
    template = env.get_template("title_agent.j2")
    return template.render(user_prompt=user_prompt, **get_template_context())


async def render_title_transcript_prompt(transcript: str, *, is_internal: bool) -> str:
    env = await get_jinja_environment_for_scope(
        scope=ChatbotVersionScope.TITLE_TRANSCRIPT, is_internal=is_internal
    )
    template = env.get_template("title_agent_transcript.j2")
    return template.render(transcript=transcript, **get_template_context())
