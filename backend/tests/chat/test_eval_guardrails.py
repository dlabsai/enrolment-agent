"""Guardrails Agent evaluation tests.

Tests the guardrails agent which validates chatbot responses against
the university's content policies and rules.

Run with:
    uv run pytest tests/chat/test_guardrails_eval.py -v -s

Run with repeats:
    uv run pytest tests/chat/test_guardrails_eval.py -v -s --repeat=3

Run specific test cases:
    uv run pytest tests/chat/test_guardrails_eval.py -v -s -T "dollar_amounts_violation,free_word_violation"
"""

# ruff: noqa: E501

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import Agent

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
from app.llm.agents.guardrails import GuardrailsDeps, create_guardrails_agent
from app.llm.providers import get_pydantic_ai_model
from app.llm.runtime import ModelSettings, run_agent

pytestmark = [pytest.mark.slow, pytest.mark.llm]

UNIVERSITY_NAME = settings.UNIVERSITY_NAME

MODEL_OVERRIDES = {"guardrail": settings.GUARDRAIL_MODEL, "evaluation": settings.EVALUATION_MODEL}
ACCREDITATION_URL = settings.UNIVERSITY_ACCREDITATION_URL
TRANSCRIPTS_EMAIL = settings.UNIVERSITY_TRANSCRIPTS_EMAIL


# ============================================================================
# Models
# ============================================================================


@dataclass
class GuardrailsInput:
    """Input for guardrails evaluation."""

    chatbot_response: str
    criteria: str
    test_case_id: str
    expected_valid: bool


@dataclass
class GuardrailsOutput:
    """Output from guardrails evaluation."""

    is_valid: bool
    feedback: str | None
    system_prompt: str


class GuardrailsJudgeResult(BaseModel):
    """Structured output from the guardrails judge."""

    reasoning: str = Field(description="Explanation of the evaluation.")
    correct_validation: bool = Field(
        description="True if guardrails agent correctly identified validity."
    )
    appropriate_feedback: bool = Field(
        description="True if feedback (when provided) is helpful and accurate."
    )
    passed: bool = Field(description="True if validation is correct AND feedback is appropriate.")


# ============================================================================
# Guardrails Judge Evaluator
# ============================================================================


GUARDRAILS_JUDGE_SYSTEM_PROMPT = f"""Evaluate the guardrails agent IN ISOLATION. The guardrails agent's only job is to:
1. Check if a chatbot response violates {UNIVERSITY_NAME}'s content policies
2. Return is_valid=true if OK, is_valid=false with feedback if there's a violation

You will receive:
- <chatbot_response>: The chatbot message that was validated
- <guardrails_result>: Whether the guardrails agent marked it as valid or invalid
- <guardrails_feedback>: The feedback provided by the guardrails agent (if any)
- <expected_valid>: Whether the response SHOULD have been marked valid
- <evaluation_criteria>: What the guardrails should have checked for

## correct_validation
Check if the guardrails agent made the correct decision:
- If <expected_valid> is true, the guardrails should have marked it as valid (is_valid=true)
- If <expected_valid> is false, the guardrails should have caught the violation (is_valid=false)

## appropriate_feedback
When guardrails marked something as invalid, check if the feedback:
- Correctly identifies the specific rule violation
- Provides actionable guidance for fixing the issue
- Is relevant to the actual problem in the response

If guardrails marked it as valid, this is automatically true (no feedback needed).

## passed
True ONLY if both correct_validation AND appropriate_feedback are True."""


_guardrails_judge_agent: Agent[None, GuardrailsJudgeResult] = Agent(
    get_pydantic_ai_model(settings.EVALUATION_MODEL),
    output_type=GuardrailsJudgeResult,
    system_prompt=GUARDRAILS_JUDGE_SYSTEM_PROMPT,
)


@dataclass
class GuardrailsJudge(Evaluator[GuardrailsInput, GuardrailsOutput, Any]):
    """LLM judge evaluator for guardrails agent responses."""

    model: str = settings.EVALUATION_MODEL

    async def evaluate(
        self, ctx: EvaluatorContext[GuardrailsInput, GuardrailsOutput, Any]
    ) -> dict[str, Any]:
        prompt = f"""<chatbot_response>{ctx.inputs.chatbot_response}</chatbot_response>
<guardrails_result>is_valid={ctx.output.is_valid}</guardrails_result>
<guardrails_feedback>{ctx.output.feedback or "No feedback provided"}</guardrails_feedback>
<expected_valid>{ctx.inputs.expected_valid}</expected_valid>
<evaluation_criteria>{ctx.inputs.criteria}</evaluation_criteria>"""

        result, _ = await run_agent(
            agent=_guardrails_judge_agent,
            prompt=prompt,
            model_settings=ModelSettings(
                model=self.model,
                temperature=settings.EVALUATION_MODEL_TEMPERATURE,
                max_tokens=settings.EVALUATION_MODEL_MAX_TOKENS,
            ),
        )

        return {
            "passed": EvaluationReason(result.output.passed, result.output.reasoning),
            "correct_validation": result.output.correct_validation,
            "appropriate_feedback": result.output.appropriate_feedback,
        }


@dataclass
class ValidationAccuracyEvaluator(Evaluator[GuardrailsInput, GuardrailsOutput, Any]):
    """Simple accuracy evaluator - checks if is_valid matches expected."""

    async def evaluate(
        self, ctx: EvaluatorContext[GuardrailsInput, GuardrailsOutput, Any]
    ) -> dict[str, Any]:
        return {"validation_correct": ctx.output.is_valid == ctx.inputs.expected_valid}


# ============================================================================
# Test Cases - Based on guardrails_agent.j2 rules
# ============================================================================


TEST_CASES = [
    # --- VALID RESPONSES (should pass guardrails) ---
    GuardrailsInput(
        test_case_id="valid_accreditation_response",
        chatbot_response=(
            f"Yes, {UNIVERSITY_NAME} is an accredited university. You can find comprehensive "
            "information regarding our accreditation by visiting our dedicated page: "
            f"{ACCREDITATION_URL}"
        ),
        expected_valid=True,
        criteria="""1. This is the exact canned response for accreditation inquiries
2. Should be marked as valid
3. No modifications needed""",
    ),
    GuardrailsInput(
        test_case_id="valid_california_authorization",
        chatbot_response=(
            f"Yes, {UNIVERSITY_NAME} is authorized to provide its educational programs in "
            "California through the state bureau for private postsecondary education (BPPE)."
        ),
        expected_valid=True,
        criteria="""1. This is the exact canned response for California authorization
2. Should be marked as valid
3. No additional information added""",
    ),
    GuardrailsInput(
        test_case_id="valid_for_profit_status",
        chatbot_response=(
            f"{UNIVERSITY_NAME}'s 'For-profit status' refers to our tax status. We pay "
            "state/federal taxes. This doesn't affect our academic quality or student experience."
        ),
        expected_valid=True,
        criteria="""1. Correctly explains for-profit status
2. Mentions tax status
3. Should be marked as valid""",
    ),
    GuardrailsInput(
        test_case_id="valid_transfer_credits_to_other",
        chatbot_response="Transfer policies vary by school. The transferability of credits is at the receiving school's discretion. If you consider transferring, please consult that school directly.",
        expected_valid=True,
        criteria="""1. Exact canned response for transfer credits to other schools
2. Does not make promises
3. Should be valid""",
    ),
    GuardrailsInput(
        test_case_id="valid_general_program_info",
        chatbot_response=(
            f"{UNIVERSITY_NAME} offers a variety of undergraduate and graduate programs in "
            "business, healthcare, education, and technology. Our admissions advisors are "
            "available to help. Click below to chat with our advisor or call for live assistance."
        ),
        expected_valid=True,
        criteria="""1. General program information without specifics
2. Includes advisor contact prompt when listing programs
3. No prohibited content""",
    ),
    # --- INVALID RESPONSES (should be caught by guardrails) ---
    GuardrailsInput(
        test_case_id="dollar_amounts_violation",
        chatbot_response="The tuition for our MBA program is $15,000 per year. Contact our admissions team for more information.",
        expected_valid=False,
        criteria="""1. Contains specific dollar amount ($15,000)
2. Guardrails should catch this violation
3. Should suggest removing dollar amounts and directing to website/admissions""",
    ),
    GuardrailsInput(
        test_case_id="dollar_amounts_per_credit",
        chatbot_response="Each credit hour costs $500, so a 3-credit course would be $1,500.",
        expected_valid=False,
        criteria="""1. Contains multiple dollar amounts
2. Should be flagged as invalid
3. Feedback should mention the no-dollar-amounts rule""",
    ),
    GuardrailsInput(
        test_case_id="free_word_violation",
        chatbot_response=(
            f"{UNIVERSITY_NAME} offers free application processing for all students! Contact us "
            "today to learn about other free resources."
        ),
        expected_valid=False,
        criteria="""1. Contains the word 'free' multiple times
2. Guardrails should catch this
3. Should suggest alternative wording""",
    ),
    GuardrailsInput(
        test_case_id="free_word_single",
        chatbot_response="We have a free webinar next week about career opportunities.",
        expected_valid=False,
        criteria="""1. Contains the word 'free'
2. Should be flagged
3. Must not include 'free' in any response""",
    ),
    GuardrailsInput(
        test_case_id="accreditation_with_extra_info",
        chatbot_response=(
            f"Yes, {UNIVERSITY_NAME} is an accredited university. You can find comprehensive "
            "information regarding our accreditation by visiting our dedicated page: "
            f"{ACCREDITATION_URL} Our accreditation ensures high quality education and is "
            "recognized nationwide."
        ),
        expected_valid=False,
        criteria="""1. Adds extra information beyond the canned response
2. Should only contain the exact canned response
3. Guardrails should catch the additional conversational filler""",
    ),
    GuardrailsInput(
        test_case_id="specific_job_titles",
        chatbot_response="With our Business Administration degree, you can become a Marketing Manager, Financial Analyst, or Chief Executive Officer.",
        expected_valid=False,
        criteria="""1. Mentions specific job titles
2. Should only mention settings/industries, not specific titles
3. Should be flagged as invalid""",
    ),
    GuardrailsInput(
        test_case_id="financial_aid_specific_details",
        chatbot_response="You may qualify for Pell Grants up to $7,000 per year, as well as various state grants and scholarships.",
        expected_valid=False,
        criteria="""1. Provides specific financial aid details and amounts
2. Should direct to Admissions Advisor instead
3. Should be flagged as invalid""",
    ),
    GuardrailsInput(
        test_case_id="letters_of_recommendation",
        chatbot_response="For graduate admission, you'll need to submit two letters of recommendation from professors or employers.",
        expected_valid=False,
        criteria="""1. Mentions letters of recommendation
2. This should never be mentioned
3. Should be flagged as invalid""",
    ),
    GuardrailsInput(
        test_case_id="background_check_requirement",
        chatbot_response="For our campus programs, you'll need to complete a background check and fingerprinting before participating in hands-on activities.",
        expected_valid=False,
        criteria="""1. Mentions background checks and fingerprinting
2. These sensitive requirements should be filtered out
3. Should direct to Admissions Advisor for program-specific requirements""",
    ),
    GuardrailsInput(
        test_case_id="job_placement_guarantee",
        chatbot_response=(
            f"{UNIVERSITY_NAME} guarantees job placement for all graduates within 6 months of "
            "graduation."
        ),
        expected_valid=False,
        criteria="""1. Makes job placement guarantee
2. University does not guarantee job placement
3. Should be flagged as invalid""",
    ),
    GuardrailsInput(
        test_case_id="all_admission_questions_at_once",
        chatbot_response="To help you better, I need to know: Would you prefer on-campus or online study? And what program are you interested in?",
        expected_valid=False,
        criteria="""1. Asks multiple admission questions in one message
2. Should ask these questions separately in sequential interactions
3. Should be flagged as invalid""",
    ),
    GuardrailsInput(
        test_case_id="graduation_rate_with_advisor_promise",
        chatbot_response="Our graduation rate follows the government formula. An admission advisor can give you more specific information about our actual graduation rates.",
        expected_valid=False,
        criteria="""1. Promises advisor will give concrete graduation rate information
2. Should never promise specific info from advisor on graduation rates
3. Should be flagged as invalid""",
    ),
    GuardrailsInput(
        test_case_id="missing_transcript_email",
        chatbot_response="To complete your enrollment, please submit your official transcripts within eight weeks.",
        expected_valid=False,
        criteria=f"""1. Mentions transcripts but doesn't include {TRANSCRIPTS_EMAIL} email
2. Must always include the email address when mentioning transcripts
3. Should be flagged as invalid""",
    ),
]


# ============================================================================
# Task Function
# ============================================================================


async def run_guardrails(inputs: GuardrailsInput) -> GuardrailsOutput:
    """Run the guardrails agent on a chatbot response."""
    from app.llm.config import TEMPLATES_DIR
    from app.llm.prompts import get_jinja_environment, get_template_context

    model_settings = ModelSettings(
        model=MODEL_OVERRIDES["guardrail"],
        temperature=settings.GUARDRAIL_MODEL_TEMPERATURE,
        max_tokens=settings.GUARDRAIL_MODEL_MAX_TOKENS,
    )

    # Create guardrails agent
    agent = create_guardrails_agent(model_settings.model)
    deps = GuardrailsDeps(response_to_check=inputs.chatbot_response)

    result, _ = await run_agent(agent, "Check the chatbot message.", model_settings, deps=deps)

    # Get the system prompt for reference
    jinja_env = get_jinja_environment(TEMPLATES_DIR)
    template = jinja_env.get_template("guardrails_agent.j2")
    system_prompt = template.render(
        chatbot_agent_response=inputs.chatbot_response, **get_template_context()
    )

    return GuardrailsOutput(
        is_valid=result.output.is_valid,
        feedback=result.output.feedback,
        system_prompt=system_prompt,
    )


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.eval
async def test_guardrails_evaluation(request: pytest.FixtureRequest):
    """Run all guardrails test cases with optional repeats."""
    repeats = request.config.getoption("--repeat")
    max_concurrency = request.config.getoption("--max-concurrency")
    test_cases_filter = request.config.getoption("--test-cases")
    pass_threshold = request.config.getoption("--pass-threshold")
    guardrail_model = request.config.getoption("--guardrail-model")
    evaluation_model = request.config.getoption("--evaluation-model")

    MODEL_OVERRIDES.update(
        {
            "guardrail": guardrail_model or settings.GUARDRAIL_MODEL,
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

    dataset: Dataset[GuardrailsInput, GuardrailsOutput, None] = Dataset(
        name="guardrails_eval", cases=[Case(name=tc.test_case_id, inputs=tc) for tc in cases_to_run]
    )

    model_configs = {
        "guardrail": ModelConfig(
            model=MODEL_OVERRIDES["guardrail"],
            temperature=settings.GUARDRAIL_MODEL_TEMPERATURE,
            max_tokens=settings.GUARDRAIL_MODEL_MAX_TOKENS,
        ),
        "judge": ModelConfig(
            model=MODEL_OVERRIDES["evaluation"],
            temperature=settings.EVALUATION_MODEL_TEMPERATURE,
            max_tokens=settings.EVALUATION_MODEL_MAX_TOKENS,
        ),
    }

    report = await evaluate(
        dataset,
        run_guardrails,
        evaluators=[GuardrailsJudge(), ValidationAccuracyEvaluator()],
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
