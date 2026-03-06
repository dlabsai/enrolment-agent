from pydantic import BaseModel
from pydantic_ai import Agent

from app.llm.prompts import get_jinja_environment_for_scope, get_template_context
from app.llm.providers import get_instrumentation_settings, get_pydantic_ai_model
from app.models import ChatbotVersionScope
from app.programs import PROGRAMS


def create_variables_extraction_agent[T: BaseModel](
    model: str,
    *,
    system_prompt: str,
    output_type: type[T],
    retries: int = 3,
    name: str = "variables_extraction",
) -> Agent[None, T]:
    return Agent(
        get_pydantic_ai_model(model),
        system_prompt=system_prompt,
        output_type=output_type,
        retries=retries,
        instrument=get_instrumentation_settings(),
        name=name,
    )


async def render_variables_extraction_prompt(transcript: str) -> str:
    env = await get_jinja_environment_for_scope(
        scope=ChatbotVersionScope.RFI_EXTRACTION, is_internal=False
    )
    template = env.get_template("rfi_extraction_agent.j2")
    return template.render(programs=PROGRAMS, transcript=transcript, **get_template_context())
