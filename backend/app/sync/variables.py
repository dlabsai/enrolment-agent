import logging

from pydantic import BaseModel

from app.core.config import settings
from app.llm.agents.variables_extraction import (
    create_variables_extraction_agent,
    render_variables_extraction_prompt,
)
from app.llm.runtime import run_agent_with_span

logger = logging.getLogger(__name__)


_ProgramsLiteral = str


class ExtractionVariables(BaseModel):
    user_degree_program_of_interest: _ProgramsLiteral | None = None
    user_wants_to_study_on_campus: bool | None = None


async def _build_system_prompt(transcript: str) -> str:
    return await render_variables_extraction_prompt(transcript)


async def extract_variables(
    transcript: str, *, conversation_id: str | None = None
) -> ExtractionVariables:
    logger.debug("Extracting variables from the conversation")

    system_prompt = await _build_system_prompt(transcript)

    extraction_agent = create_variables_extraction_agent(
        settings.EXTRACTOR_MODEL, system_prompt=system_prompt, output_type=ExtractionVariables
    )

    try:
        agent_result = await run_agent_with_span(
            extraction_agent,
            prompt="",
            span_name="extract_conversation_variables",
            agent_name="variables_extraction",
            is_internal=False,
            conversation_id=conversation_id,
        )
    except Exception:
        logger.exception("Error extracting variables")
        return ExtractionVariables()
    else:
        logger.debug("Variables extracted successfully")
        return agent_result.output
