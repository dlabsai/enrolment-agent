from pydantic_ai import Agent

from app.chat.tools import Deps
from app.llm.prompts import get_template_context
from app.llm.providers import get_instrumentation_settings, get_pydantic_ai_model
from app.llm.text import normalize_whitespace


def render_search_prompt(deps: Deps) -> str:
    template = deps.jinja_env.get_template("search_agent.j2")
    return normalize_whitespace(template.render(**get_template_context()))


def create_search_agent(
    model: str, deps: Deps, system_prompt: str | None = None, *, name: str = "search"
) -> Agent[Deps, str]:
    if system_prompt is None:
        system_prompt = render_search_prompt(deps)

    pydantic_model = get_pydantic_ai_model(model)

    return Agent(
        pydantic_model,
        output_type=str,
        deps_type=Deps,
        tools=deps.tools,
        system_prompt=system_prompt,
        instrument=get_instrumentation_settings(),
        name=name,
    )
