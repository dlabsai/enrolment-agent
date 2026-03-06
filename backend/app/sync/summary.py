import logging

from app.core.config import settings
from app.llm.agents.summary import create_summary_agent, render_summary_prompt
from app.llm.runtime import run_agent_with_span

logger = logging.getLogger(__name__)


async def summarize_conversation(transcript: str, *, conversation_id: str | None = None) -> str:
    logger.debug("Generating conversation summary")

    prompt = await render_summary_prompt(transcript, is_internal=False)

    try:
        agent = create_summary_agent(settings.SUMMARIZER_MODEL, name="conversation_summary")
        result = await run_agent_with_span(
            agent,
            prompt=prompt,
            span_name="summarize_sync",
            agent_name="conversation_summary",
            is_internal=False,
            conversation_id=conversation_id,
        )
        summary = result.output

    except Exception:
        logger.exception("Error generating summary")
        return "Summary generation failed. Please review the full transcript for details."
    else:
        logger.debug(f"Summary generated successfully ({len(summary)} characters)")
        return summary
