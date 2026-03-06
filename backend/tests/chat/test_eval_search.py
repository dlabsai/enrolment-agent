"""Search Agent evaluation tests.

Tests the search agent which gathers information from the university's
website using RAG tools before the chatbot generates responses.

Run with:
    uv run pytest tests/chat/test_search_agent_eval.py -v -s

Run with repeats:
    uv run pytest tests/chat/test_search_agent_eval.py -v -s --repeat=3

Run specific test cases:
    uv run pytest tests/chat/test_search_agent_eval.py -v -s -T "program_inquiry,tuition_question"

Note: This test requires the RAG database to be populated with test data.
Use `--rebuild-rag` flag if needed to refresh RAG data.
"""

# ruff: noqa: E501

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.chat.tools import Deps, get_deps
from app.core.config import settings
from app.evals import (
    Case,
    Dataset,
    EvaluationReason,
    Evaluator,
    EvaluatorContext,
    ModelConfig,
    evaluate,
)
from app.llm.agents.search import create_search_agent
from app.llm.providers import get_pydantic_ai_model
from app.llm.runtime import ModelSettings, run_agent

pytestmark = [pytest.mark.slow, pytest.mark.llm]

UNIVERSITY_NAME = settings.UNIVERSITY_NAME
TRANSCRIPTS_EMAIL = settings.UNIVERSITY_TRANSCRIPTS_EMAIL

MODEL_OVERRIDES = {"search": settings.SEARCH_AGENT_MODEL, "evaluation": settings.EVALUATION_MODEL}


# ============================================================================
# Models
# ============================================================================


@dataclass
class SearchAgentInput:
    """Input for search agent evaluation."""

    user_query: str
    criteria: str
    test_case_id: str


@dataclass
class SearchAgentOutput:
    """Output from search agent evaluation."""

    search_response: str
    system_prompt: str
    tool_calls_made: int


class SearchAgentJudgeResult(BaseModel):
    """Structured output from the search agent judge."""

    reasoning: str = Field(description="Explanation of the evaluation.")
    used_tools: bool = Field(description="True if the agent used tools to retrieve information.")
    relevant_information: bool = Field(
        description="True if the response contains relevant information for the query."
    )
    grounded_response: bool = Field(
        description="True if the response is based on tool results, not general knowledge."
    )
    passed: bool = Field(
        description="True if used_tools AND relevant_information AND grounded_response."
    )


# ============================================================================
# Search Agent Judge Evaluator
# ============================================================================


SEARCH_AGENT_JUDGE_SYSTEM_PROMPT = f"""Evaluate the search agent IN ISOLATION. The search agent's only job is to:
1. Use RAG tools to retrieve information from {UNIVERSITY_NAME}'s website
2. Provide a summary of the retrieved content
3. NOT rely on general knowledge about universities

You will receive:
- <user_query>: The user's question or request
- <search_response>: The search agent's response
- <tool_calls_made>: Number of tool calls the agent made
- <system_prompt>: The search agent's system prompt/instructions
- <evaluation_criteria>: Specific criteria to check

## used_tools
Check if the agent used tools to retrieve information:
- If tool_calls_made > 0, this is true
- The search agent MUST use tools - it should never answer from general knowledge

## relevant_information
Check if the response contains information relevant to the query:
- Does it address what the user asked?
- Does it include specific details from {UNIVERSITY_NAME}'s data?
- For program queries: does it list actual programs?
- For tuition queries: does it reference cost information (without specific amounts)?

## grounded_response
Check if the response is based on retrieved data:
- Does it sound like it came from tool results?
- Does it avoid generic university information?
- Does it acknowledge when information wasn't found?

## passed
True ONLY if all three criteria are met."""


_search_agent_judge: Agent[None, SearchAgentJudgeResult] = Agent(
    get_pydantic_ai_model(settings.EVALUATION_MODEL),
    output_type=SearchAgentJudgeResult,
    system_prompt=SEARCH_AGENT_JUDGE_SYSTEM_PROMPT,
)


@dataclass
class SearchAgentJudge(Evaluator[SearchAgentInput, SearchAgentOutput, Any]):
    """LLM judge evaluator for search agent responses."""

    model: str = settings.EVALUATION_MODEL

    async def evaluate(
        self, ctx: EvaluatorContext[SearchAgentInput, SearchAgentOutput, Any]
    ) -> dict[str, Any]:
        prompt = f"""<user_query>{ctx.inputs.user_query}</user_query>
<search_response>{ctx.output.search_response}</search_response>
<tool_calls_made>{ctx.output.tool_calls_made}</tool_calls_made>
<system_prompt>{ctx.output.system_prompt}</system_prompt>
<evaluation_criteria>{ctx.inputs.criteria}</evaluation_criteria>"""

        result, _ = await run_agent(
            agent=_search_agent_judge,
            prompt=prompt,
            model_settings=ModelSettings(
                model=self.model,
                temperature=settings.EVALUATION_MODEL_TEMPERATURE,
                max_tokens=settings.EVALUATION_MODEL_MAX_TOKENS,
            ),
        )

        return {
            "passed": EvaluationReason(result.output.passed, result.output.reasoning),
            "used_tools": result.output.used_tools,
            "relevant_information": result.output.relevant_information,
            "grounded_response": result.output.grounded_response,
        }


@dataclass
class ToolUsageEvaluator(Evaluator[SearchAgentInput, SearchAgentOutput, Any]):
    """Simple evaluator checking if tools were used."""

    async def evaluate(
        self, ctx: EvaluatorContext[SearchAgentInput, SearchAgentOutput, Any]
    ) -> dict[str, Any]:
        return {
            "tool_calls_count": float(ctx.output.tool_calls_made),
            "used_tools": ctx.output.tool_calls_made > 0,
        }


# ============================================================================
# Test Cases - Based on search_agent.j2 instructions
# ============================================================================


TEST_CASES = [
    # --- Program Information Queries ---
    SearchAgentInput(
        test_case_id="program_inquiry_general",
        user_query=f"What programs does {UNIVERSITY_NAME} offer?",
        criteria=f"""1. Must use tools to search for programs
2. Should list actual programs from {UNIVERSITY_NAME}
3. Should not rely on general knowledge about typical university programs
4. Should include both undergraduate and graduate options
5. Should offer to narrow down based on interests""",
    ),
    SearchAgentInput(
        test_case_id="program_inquiry_business",
        user_query="Do you have any business programs?",
        criteria="""1. Must search for business-related programs
2. Should find business, management, or related programs
3. Should include program levels (BS, MBA, etc.)
4. Should be based on actual search results""",
    ),
    SearchAgentInput(
        test_case_id="program_inquiry_technology",
        user_query="What computer science or technology programs do you have?",
        criteria="""1. Must search for technology/CS programs
2. Should find IT, computer science, cybersecurity, or similar
3. Should include multiple related programs
4. Should use broad semantic matching""",
    ),
    SearchAgentInput(
        test_case_id="program_inquiry_education",
        user_query="I want to become a teacher. What programs do you have?",
        criteria="""1. Must search for education programs
2. Should find teaching, education, or pedagogy programs
3. Should mention certification paths if available
4. Must not rely on assumptions""",
    ),
    # --- Specific Information Queries ---
    SearchAgentInput(
        test_case_id="tuition_question",
        user_query="How much does tuition cost?",
        criteria="""1. Must search for tuition information
2. Should find cost-related information
3. Should direct to admissions for specific figures
4. Should not make up dollar amounts""",
    ),
    SearchAgentInput(
        test_case_id="financial_aid_question",
        user_query="What financial aid options are available?",
        criteria="""1. Must search for financial aid information
2. Should find general financial aid info
3. Should reference official sources
4. Should not provide specific grant amounts""",
    ),
    SearchAgentInput(
        test_case_id="admission_requirements",
        user_query="What are the admission requirements?",
        criteria="""1. Must search for admission requirements
2. Should find general admission process information
3. May acknowledge different requirements by program
4. Should not mention sensitive requirements (background checks)""",
    ),
    SearchAgentInput(
        test_case_id="accreditation_question",
        user_query=f"Is {UNIVERSITY_NAME} accredited?",
        criteria="""1. Must search for accreditation information
2. Should find official accreditation details
3. Should reference the accrediting agency if found
4. Should be based on search results""",
    ),
    SearchAgentInput(
        test_case_id="online_vs_campus",
        user_query="Can I take classes online or do I need to go to campus?",
        criteria="""1. Must search for online/campus options
2. Should find information about both modalities
3. Should explain the options available
4. Must be grounded in search results""",
    ),
    # --- Complex/Ambiguous Queries ---
    SearchAgentInput(
        test_case_id="career_outcomes",
        user_query=f"What kind of jobs can I get with a {UNIVERSITY_NAME} degree?",
        criteria="""1. Must search for career-related information
2. Should find career services or outcomes info
3. Should not list specific job titles
4. Should mention settings/industries instead""",
    ),
    SearchAgentInput(
        test_case_id="transfer_credits",
        user_query="Can I transfer credits from another school?",
        criteria=f"""1. Must search for transfer credit information
2. Should find credit evaluation process
3. Should mention transcript requirements
4. Should include {TRANSCRIPTS_EMAIL} if enrollment-related""",
    ),
    SearchAgentInput(
        test_case_id="start_dates",
        user_query="When can I start classes?",
        criteria="""1. Must search for start date information
2. Should find term/semester start information
3. Should be specific if data is available
4. Should not make up dates""",
    ),
    # --- Edge Cases ---
    SearchAgentInput(
        test_case_id="vague_query",
        user_query=f"Tell me about {UNIVERSITY_NAME}",
        criteria="""1. Must use tools to gather general information
2. Should provide overview information
3. Should cover multiple relevant topics
4. Should acknowledge this is a broad query""",
    ),
    SearchAgentInput(
        test_case_id="specific_degree",
        user_query="Tell me about the MBA program",
        criteria="""1. Must search for MBA-specific information
2. Should find MBA program details
3. Should include curriculum or focus areas if available
4. Must be grounded in search results""",
    ),
]


# ============================================================================
# Task Function
# ============================================================================


async def run_search_agent(inputs: SearchAgentInput) -> SearchAgentOutput:
    """Run the search agent on a user query.

    Note: This requires RAG data to be populated in the test database.
    """
    from pydantic_ai.messages import ToolCallPart

    from app.llm.config import TEMPLATES_DIR
    from app.llm.prompts import get_jinja_environment, get_template_context

    model_settings = ModelSettings(
        model=MODEL_OVERRIDES["search"],
        temperature=settings.SEARCH_AGENT_MODEL_TEMPERATURE,
        max_tokens=settings.SEARCH_AGENT_MODEL_MAX_TOKENS,
    )

    # Create deps and search agent
    deps: Deps = get_deps(is_internal=False)  # Public mode
    agent = create_search_agent(model_settings.model, deps)

    result, _ = await run_agent(agent, inputs.user_query, model_settings, deps=deps)

    # Count tool calls
    tool_calls_made = 0
    for msg in result.all_messages():
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    tool_calls_made += 1

    # Get system prompt
    jinja_env = get_jinja_environment(TEMPLATES_DIR)
    template = jinja_env.get_template("search_agent.j2")
    system_prompt = template.render(**get_template_context())

    return SearchAgentOutput(
        search_response=result.output, system_prompt=system_prompt, tool_calls_made=tool_calls_made
    )


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.eval
async def test_search_agent_evaluation(db_engine: object, request: pytest.FixtureRequest):
    """Run all search agent test cases with optional repeats.

    Requires db_engine fixture to ensure RAG data is available.
    """
    repeats = request.config.getoption("--repeat")
    max_concurrency = request.config.getoption("--max-concurrency")
    test_cases_filter = request.config.getoption("--test-cases")
    pass_threshold = request.config.getoption("--pass-threshold")
    search_model = request.config.getoption("--search-model")
    evaluation_model = request.config.getoption("--evaluation-model")

    MODEL_OVERRIDES.update(
        {
            "search": search_model or settings.SEARCH_AGENT_MODEL,
            "evaluation": evaluation_model or settings.EVALUATION_MODEL,
        }
    )

    # Filter test cases if specified
    cases_to_run = TEST_CASES
    if test_cases_filter:
        selected_ids = {tc.strip() for tc in test_cases_filter.split(",")}
        cases_to_run = [tc for tc in TEST_CASES if tc.test_case_id in selected_ids]
        if not cases_to_run:
            pytest.fail(f"No matching test cases found for: {test_cases_filter}")

    dataset: Dataset[SearchAgentInput, SearchAgentOutput, None] = Dataset(
        name="search_agent_eval",
        cases=[Case(name=tc.test_case_id, inputs=tc) for tc in cases_to_run],
    )

    model_configs = {
        "search_agent": ModelConfig(
            model=MODEL_OVERRIDES["search"],
            temperature=settings.SEARCH_AGENT_MODEL_TEMPERATURE,
            max_tokens=settings.SEARCH_AGENT_MODEL_MAX_TOKENS,
        ),
        "judge": ModelConfig(
            model=MODEL_OVERRIDES["evaluation"],
            temperature=settings.EVALUATION_MODEL_TEMPERATURE,
            max_tokens=settings.EVALUATION_MODEL_MAX_TOKENS,
        ),
    }

    report = await evaluate(
        dataset,
        run_search_agent,
        evaluators=[SearchAgentJudge(), ToolUsageEvaluator()],
        repeats=repeats,
        max_concurrency=max_concurrency,
        model_configs=model_configs,
    )

    report.print_summary()
    report.write_report()

    # Check results
    failed = [
        c for c in report.cases if c.stats.assertion_pass_rates.get("passed", 0) < pass_threshold
    ]
    if failed:
        summary = "\n".join(
            f"  {c.name}: {c.stats.assertion_pass_rates.get('passed', 0):.0%} "
            f"(threshold: {pass_threshold:.0%})"
            for c in failed
        )
        pytest.fail(
            f"Failed {len(failed)}/{len(report.cases)} cases "
            f"(threshold: {pass_threshold:.0%}):\n{summary}",
            pytrace=False,
        )
