"""LLM Judge evaluation tests with repeat and concurrency support.

Tests the full chatbot pipeline (extractor + chatbot + guardrails) using
LLM-based evaluation to assess response quality.

Run with:
    uv run pytest tests/chat/test_llm_judge.py -v -s

Run with repeats (sequential by default):
    uv run pytest tests/chat/test_llm_judge.py -v -s --repeat=3

Run with parallel repeats:
    uv run pytest tests/chat/test_llm_judge.py -v -s --repeat=5 --max-concurrency=5

Run with custom pass threshold (default is 90%):
    uv run pytest tests/chat/test_llm_judge.py -v -s -R 5 -C 5 --pass-threshold=0.8

Run specific test cases:
    uv run pytest tests/chat/test_llm_judge.py -v -s -T "greeting_response,accreditation_inquiry"
"""

# ruff: noqa: E501

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.chat.engine import MessageOut, handle_conversation_turn
from app.core.config import settings
from app.core.db import async_session_factory
from app.evals import (
    Case,
    Dataset,
    EvaluationReason,
    Evaluator,
    EvaluatorContext,
    ModelConfig,
    evaluate,
)
from app.llm.providers import get_pydantic_ai_model
from app.llm.runtime import ModelSettings, run_agent
from app.models import User

pytestmark = [pytest.mark.slow, pytest.mark.llm]

UNIVERSITY_NAME = settings.UNIVERSITY_NAME
ACCREDITATION_URL = settings.UNIVERSITY_ACCREDITATION_URL
APPLICATION_URL = settings.UNIVERSITY_APPLICATION_URL

MODEL_OVERRIDES = {
    "chatbot": settings.CHATBOT_MODEL,
    "extractor": settings.EXTRACTOR_MODEL,
    "guardrail": settings.GUARDRAIL_MODEL,
    "search": settings.SEARCH_AGENT_MODEL,
    "evaluation": settings.EVALUATION_MODEL,
}


# ============================================================================
# Models
# ============================================================================


@dataclass
class ChatbotInput:
    """Input for chatbot evaluation."""

    user_input: str
    criteria: str
    test_case_id: str
    is_internal: bool = False


@dataclass
class ChatbotOutput:
    """Output from chatbot evaluation."""

    chatbot_response: str
    system_prompt: str
    guardrail_retries: int = 0


class ChatbotJudgeResult(BaseModel):
    """Structured output from the chatbot LLM judge."""

    reasoning: str = Field(description="Explanation of the evaluation.")
    follows_guidelines: bool = Field(description="True if response follows all criteria.")
    is_grounded: bool = Field(description="True if response is grounded in context.")
    passed: bool = Field(description="True if response follows guidelines AND is grounded.")


# ============================================================================
# LLM Judge Evaluator
# ============================================================================


CHATBOT_JUDGE_SYSTEM_PROMPT = """Evaluate a university chatbot response.

You will receive:
- <user_input>: The user's message to the chatbot
- <chatbot_response>: The chatbot's final response to evaluate
- <chatbot_system_prompt>: The system prompt that was used to generate the response (contains rules, RAG search results, etc.)
- <evaluation_criteria>: Specific criteria to check

## CRITICAL: Understanding the System Prompt Structure

The <chatbot_system_prompt> may contain a section called <guardrails_agent_feedback>.
This feedback describes issues with a PREVIOUS response that was already corrected.
The <chatbot_response> you are evaluating is the FINAL response AFTER any corrections were made.

DO NOT attribute content from <guardrails_agent_feedback> to <chatbot_response>.
Only evaluate what is ACTUALLY written in <chatbot_response>.

## follows_guidelines
- Check EACH numbered criterion explicitly against the ACTUAL text in <chatbot_response>
- Be literal and strict about requirements
- Also check canned response rules defined in <chatbot_system_prompt>
- IMPORTANT: Only evaluate the literal content of <chatbot_response>, not content mentioned in guardrails feedback

## is_grounded
The response should only contain information from:
- The rules and canned responses in <chatbot_system_prompt>
- The <search-results> section (RAG data) within <chatbot_system_prompt>
- The user's own message

## passed
True ONLY if both follows_guidelines AND is_grounded are True."""


# Create judge agent once at module level to avoid httpx client cleanup issues
_chatbot_judge_agent: Agent[None, ChatbotJudgeResult] = Agent(
    get_pydantic_ai_model(settings.EVALUATION_MODEL),
    output_type=ChatbotJudgeResult,
    system_prompt=CHATBOT_JUDGE_SYSTEM_PROMPT,
)


@dataclass
class ChatbotJudge(Evaluator[ChatbotInput, ChatbotOutput, Any]):
    """LLM judge evaluator for chatbot responses.

    Evaluates the full chatbot pipeline output including:
    - Whether the response follows the specified guidelines
    - Whether the response is grounded in the system prompt context
    """

    model: str = settings.EVALUATION_MODEL

    async def evaluate(
        self, ctx: EvaluatorContext[ChatbotInput, ChatbotOutput, Any]
    ) -> dict[str, Any]:
        prompt = f"""<user_input>{ctx.inputs.user_input}</user_input>
<chatbot_response>{ctx.output.chatbot_response}</chatbot_response>
<chatbot_system_prompt>{ctx.output.system_prompt}</chatbot_system_prompt>
<evaluation_criteria>{ctx.inputs.criteria}</evaluation_criteria>"""

        result, _ = await run_agent(
            agent=_chatbot_judge_agent,
            prompt=prompt,
            model_settings=ModelSettings(
                model=self.model,
                temperature=settings.EVALUATION_MODEL_TEMPERATURE,
                max_tokens=settings.EVALUATION_MODEL_MAX_TOKENS,
            ),
        )

        return {
            "passed": EvaluationReason(result.output.passed, result.output.reasoning),
            "follows_guidelines": result.output.follows_guidelines,
            "is_grounded": result.output.is_grounded,
        }


@dataclass
class MetricsExtractor(Evaluator[ChatbotInput, ChatbotOutput, Any]):
    """Extracts metrics from chatbot output as scores."""

    async def evaluate(
        self, ctx: EvaluatorContext[ChatbotInput, ChatbotOutput, Any]
    ) -> dict[str, Any]:
        return {"guardrail_retries": float(ctx.output.guardrail_retries)}


# ============================================================================
# Test Cases
# ============================================================================


TEST_CASES = [
    # Basic interactions
    ChatbotInput(
        test_case_id="greeting_response",
        user_input="hi",
        criteria=f"""1. Warm, friendly, welcoming response
2. Introduce bot as {UNIVERSITY_NAME} enrollment agent
3. Offer to help or ask how it can assist
4. Enthusiastic but professional tone""",
    ),
    ChatbotInput(
        test_case_id="program_inquiry_general",
        user_input="What programs do you offer?",
        criteria=f"""1. Acknowledge the question about programs
2. Mention {UNIVERSITY_NAME} offers various programs
3. List programs OR ask clarifying questions
4. Be helpful and encourage engagement""",
    ),
    # Canned responses
    ChatbotInput(
        test_case_id="accreditation_inquiry",
        user_input=f"Is {UNIVERSITY_NAME} accredited?",
        criteria=f"""1. MUST contain: "Yes, {UNIVERSITY_NAME} is an accredited university"
2. MUST include link: {ACCREDITATION_URL}
3. Should NOT add extra conversational filler
4. Should NOT propose contact about accreditation""",
    ),
    ChatbotInput(
        test_case_id="california_authorization",
        user_input=f"Is {UNIVERSITY_NAME} authorized to operate in California?",
        criteria=f"""1. MUST mention state bureau for private postsecondary education (BPPE)
2. Confirm {UNIVERSITY_NAME} is authorized in California
3. Should NOT add extra conversational filler""",
    ),
    ChatbotInput(
        test_case_id="for_profit_status",
        user_input=f"Is {UNIVERSITY_NAME} a for-profit school?",
        criteria="""1. Explain that 'for-profit status' refers to tax status
2. Mention that the university pays state/federal taxes
3. Clarify this doesn't affect academic quality or student experience""",
    ),
    ChatbotInput(
        test_case_id="transfer_credits_to_other_schools",
        user_input=f"Will my {UNIVERSITY_NAME} credits transfer to other schools?",
        criteria="""1. Explain that transfer policies vary by school
2. Mention transferability is at the receiving school's discretion
3. Advise consulting the receiving school directly
4. Should NOT make promises about credit transferability""",
    ),
    ChatbotInput(
        test_case_id="payment_plan_options",
        user_input="Do you offer payment plans?",
        criteria="""1. Mention flexible monthly payment plans
2. Mention spreading tuition costs over monthly installments
3. Mention Financial Aid Advisor working directly with students
4. Propose contact with admission office""",
    ),
    # Admissions
    ChatbotInput(
        test_case_id="application_link",
        user_input=f"I want to apply to {UNIVERSITY_NAME}",
        criteria=f"""1. MUST include URL: {APPLICATION_URL}
2. URL must include tracking parameters (utm_source=VA)
3. Be encouraging about the application process""",
    ),
    # Redirects
    ChatbotInput(
        test_case_id="financial_aid_redirect",
        user_input="Can you tell me about grants and scholarships available?",
        criteria="""1. Should NOT provide specific financial aid details or amounts
2. Direct user to contact an Admissions Advisor for funding options
3. Explain Admissions Advisors are the appropriate resource
4. Helpful tone, not dismissive""",
    ),
    # Guardrails
    ChatbotInput(
        test_case_id="no_dollar_amounts",
        user_input="How much does tuition cost per semester?",
        criteria="""1. Should NOT include specific dollar amounts
2. Direct to website or admission office for exact figures
3. Acknowledge question is about costs
4. Be helpful despite not providing numbers""",
    ),
    ChatbotInput(
        test_case_id="no_free_word",
        user_input="Tell me about financial assistance options",
        criteria="""1. Should NOT contain the word "free"
2. Can discuss financial assistance, aid, or support
3. Should be helpful regarding financial topics""",
    ),
]


# ============================================================================
# Task Function
# ============================================================================


async def run_chatbot(inputs: ChatbotInput) -> ChatbotOutput:
    """Call the chatbot and return response with context.

    Each run creates its own user, runs the chatbot, then rolls back.
    RAG data stays intact since it was committed separately.
    """
    chatbot_settings = ModelSettings(
        model=MODEL_OVERRIDES["chatbot"],
        temperature=settings.CHATBOT_MODEL_TEMPERATURE,
        max_tokens=settings.CHATBOT_MODEL_MAX_TOKENS,
    )
    guardrail_settings = ModelSettings(
        model=MODEL_OVERRIDES["guardrail"],
        temperature=settings.GUARDRAIL_MODEL_TEMPERATURE,
        max_tokens=settings.GUARDRAIL_MODEL_MAX_TOKENS,
    )
    search_settings = ModelSettings(
        model=MODEL_OVERRIDES["search"],
        temperature=settings.SEARCH_AGENT_MODEL_TEMPERATURE,
        max_tokens=settings.SEARCH_AGENT_MODEL_MAX_TOKENS,
    )

    system_prompt_holder: dict[str, str] = {}

    def capture_system_prompt(prompt: str, iteration: int | None) -> None:
        system_prompt_holder["value"] = prompt

    async with async_session_factory() as session:
        # Create a unique test user for this run
        test_user = User(
            id=uuid.uuid4(),
            email=f"test-{uuid.uuid4()}@example.com",
            name="Test User",
            password_hash="not-a-real-hash",  # noqa: S106
            is_active=True,
        )
        session.add(test_user)
        await session.flush()

        _, assistant_message = await handle_conversation_turn(
            conversation_id=None,
            parent_message_id=None,
            user_prompt=inputs.user_input,
            is_regeneration=False,
            chatbot_model_settings=chatbot_settings,
            guardrail_model_settings=guardrail_settings,
            search_model_settings=search_settings,
            user_id=test_user.id,
            session=session,
            is_internal=inputs.is_internal,
            enable_guardrails=settings.ENABLE_GUARDRAILS,
            max_guardrails_retries=settings.MAX_GUARDRAILS_RETRIES,
            system_prompt_emitter=capture_system_prompt,
        )

        assert isinstance(assistant_message, MessageOut)

        output = ChatbotOutput(
            chatbot_response=assistant_message.content,
            system_prompt=system_prompt_holder.get("value", ""),
            guardrail_retries=0,
        )

        # Rollback - don't persist user/conversation data
        await session.rollback()

    return output


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.eval
async def test_chatbot_evaluation(db_engine: object, request: pytest.FixtureRequest):
    """Run all test cases with optional repeats for statistical confidence."""
    repeats = request.config.getoption("--repeat")
    max_concurrency = request.config.getoption("--max-concurrency")
    test_cases_filter = request.config.getoption("--test-cases")
    pass_threshold = request.config.getoption("--pass-threshold")
    chatbot_model = request.config.getoption("--chatbot-model")
    guardrail_model = request.config.getoption("--guardrail-model")
    search_model = request.config.getoption("--search-model")
    extractor_model = request.config.getoption("--extractor-model")
    evaluation_model = request.config.getoption("--evaluation-model")

    MODEL_OVERRIDES.update(
        {
            "chatbot": chatbot_model or settings.CHATBOT_MODEL,
            "extractor": extractor_model or settings.EXTRACTOR_MODEL,
            "guardrail": guardrail_model or settings.GUARDRAIL_MODEL,
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

    dataset: Dataset[ChatbotInput, ChatbotOutput, None] = Dataset(
        name="va_chatbot_eval", cases=[Case(name=tc.test_case_id, inputs=tc) for tc in cases_to_run]
    )

    # Build model configs for reporting
    model_configs = {
        "extractor": ModelConfig(
            model=MODEL_OVERRIDES["extractor"],
            temperature=settings.EXTRACTOR_MODEL_TEMPERATURE,
            max_tokens=settings.EXTRACTOR_MODEL_MAX_TOKENS,
        ),
        "chatbot": ModelConfig(
            model=MODEL_OVERRIDES["chatbot"],
            temperature=settings.CHATBOT_MODEL_TEMPERATURE,
            max_tokens=settings.CHATBOT_MODEL_MAX_TOKENS,
        ),
        "guardrail": ModelConfig(
            model=MODEL_OVERRIDES["guardrail"],
            temperature=settings.GUARDRAIL_MODEL_TEMPERATURE,
            max_tokens=settings.GUARDRAIL_MODEL_MAX_TOKENS,
        ),
        "search": ModelConfig(
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

    additional_settings = {
        "enable_guardrails": settings.ENABLE_GUARDRAILS,
        "max_guardrails_retries": settings.MAX_GUARDRAILS_RETRIES,
    }

    report = await evaluate(
        dataset,
        run_chatbot,
        evaluators=[ChatbotJudge(), MetricsExtractor()],
        repeats=repeats,
        max_concurrency=max_concurrency,
        model_configs=model_configs,
        additional_settings=additional_settings,
    )

    report.print_summary()
    report.write_report()

    # Check results - each case must meet the pass threshold
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
