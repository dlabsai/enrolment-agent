from collections.abc import Sequence

from jinja2 import Template
from pydantic_ai import Agent
from pydantic_ai.tools import Tool, ToolFuncEither

from app.chat.tools import Deps
from app.llm.prompts import get_template_context
from app.llm.providers import get_instrumentation_settings, get_pydantic_ai_model
from app.llm.text import normalize_whitespace

type ChatbotTool = Tool[Deps] | ToolFuncEither[Deps, ...]


def create_chatbot_agent(
    model: str,
    tools: Sequence[ChatbotTool] | None = None,
    system_prompt: str = "",
    *,
    name: str = "chatbot",
) -> Agent[Deps, str]:
    pydantic_model = get_pydantic_ai_model(model)

    return Agent(
        pydantic_model,
        output_type=str,
        deps_type=Deps,
        tools=tools or [],
        system_prompt=system_prompt,
        instrument=get_instrumentation_settings(),
        name=name,
    )


def render_chatbot_prompt(
    template: Template,
    *,
    current_date: str,
    guardrails_agent_response: str,
    search_agent_response: str,
) -> str:
    prompt = template.render(
        current_date=current_date,
        guardrails_agent_response=guardrails_agent_response,
        search_agent_response=search_agent_response,
        **get_template_context(),
    )
    return normalize_whitespace(prompt)
