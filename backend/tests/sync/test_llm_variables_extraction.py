"""Tests for variables extraction."""

# TODO: check if still needed

import pytest

from app.evals import Case, Dataset, Evaluator, EvaluatorContext, evaluate
from app.evals.evaluator import EvaluatorOutput
from app.sync.variables import ExtractionVariables, extract_variables

pytestmark = [pytest.mark.slow, pytest.mark.llm]


class EqualsExpectedEvaluator(Evaluator[str, ExtractionVariables, None]):
    """Evaluator that checks if output equals expected output."""

    @property
    def name(self) -> str:
        return "equals_expected"

    async def evaluate(
        self, ctx: EvaluatorContext[str, ExtractionVariables, None]
    ) -> EvaluatorOutput:
        output = ctx.output
        expected = ctx.expected_output

        if expected is None:
            return {"equals_expected": True}

        return {
            "equals_expected": output == expected,
            "program_match": (
                output.user_degree_program_of_interest  # pyright: ignore[reportUnknownMemberType]
                == expected.user_degree_program_of_interest  # pyright: ignore[reportUnknownMemberType]
            ),
            "campus_match": output.user_wants_to_study_on_campus
            == expected.user_wants_to_study_on_campus,
        }


TEST_CASES: list[Case[str, ExtractionVariables, None]] = [
    Case(
        name="full-signal",
        inputs=(
            "Advisor: Thanks for sharing your goals.\n"
            "User: I'm looking at the Software Engineering, BS program.\n"
            "User: I definitely want to study on campus."
        ),
        expected_output=ExtractionVariables(
            user_degree_program_of_interest="Software Engineering, BS",
            user_wants_to_study_on_campus=True,
        ),
    ),
    Case(
        name="online-preference",
        inputs=(
            "User: I'm planning to enroll in the Business Administration, BS program.\n"
            "User: I prefer to stay online rather than come to campus."
        ),
        expected_output=ExtractionVariables(
            user_degree_program_of_interest="Business Administration, BS",
            user_wants_to_study_on_campus=False,
        ),
    ),
    Case(
        name="no-signal",
        inputs=(
            "User: I'm still exploring options and just wanted to chat about possibilities.\n"
            "User: I don't have a program picked yet and am unsure about format."
        ),
        expected_output=ExtractionVariables(),
    ),
]


@pytest.mark.asyncio
async def test_variables_extraction(request: pytest.FixtureRequest):
    """Run variables extraction evaluation."""
    repeats = request.config.getoption("--repeat")
    max_concurrency = request.config.getoption("--max-concurrency")

    dataset: Dataset[str, ExtractionVariables, None] = Dataset(
        name="variables_extraction", cases=TEST_CASES
    )

    async def task(transcript: str) -> ExtractionVariables:
        return await extract_variables(transcript)

    report = await evaluate(
        dataset,
        task,
        evaluators=[EqualsExpectedEvaluator()],
        repeats=repeats,
        max_concurrency=max_concurrency,
    )

    report.print_summary()

    # Check results
    failed = [
        c for c in report.cases if c.stats.assertion_pass_rates.get("equals_expected", 0) < 1.0
    ]
    if failed:
        summary = "\n".join(
            f"  {c.name}: {c.stats.assertion_pass_rates.get('equals_expected', 0):.0%}"
            for c in failed
        )
        pytest.fail(f"Failed {len(failed)}/{len(report.cases)} cases:\n{summary}")
