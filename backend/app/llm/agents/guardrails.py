from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from app.llm.prompts import get_template_context, resolve_jinja_environment
from app.llm.providers import get_instrumentation_settings, get_pydantic_ai_model


@dataclass
class GuardrailsDeps:
    response_to_check: str = ""


class GuardrailsResult(BaseModel):
    is_valid: bool = Field(
        description="True if the chatbot response is valid and follows all rules, "
        "False if it requires revision."
    )
    feedback: str | None = Field(
        default=None,
        description="If is_valid is False, provide the reason and instructions for the "
        "necessary changes. If is_valid is True, this should be None.",
    )


def render_guardrails_prompt(
    response_to_check: str, *, is_internal: bool, db_templates: dict[str, str] | None = None
) -> str:
    env = resolve_jinja_environment(is_internal=is_internal, db_templates=db_templates)
    template = env.get_template("guardrails_agent.j2")
    return template.render(chatbot_agent_response=response_to_check, **get_template_context())


def create_guardrails_agent(
    model: str,
    *,
    is_internal: bool = False,
    db_templates: dict[str, str] | None = None,
    name: str = "guardrails",
) -> Agent[GuardrailsDeps, GuardrailsResult]:
    pydantic_model = get_pydantic_ai_model(model)

    agent: Agent[GuardrailsDeps, GuardrailsResult] = Agent(
        pydantic_model,
        output_type=GuardrailsResult,
        deps_type=GuardrailsDeps,
        instrument=get_instrumentation_settings(),
        name=name,
    )

    @agent.system_prompt
    def _get_system_prompt(ctx: RunContext[GuardrailsDeps]) -> str:  # pyright: ignore[reportUnusedFunction]
        return render_guardrails_prompt(
            ctx.deps.response_to_check, is_internal=is_internal, db_templates=db_templates
        )

    return agent
