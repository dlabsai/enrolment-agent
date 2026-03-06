"""Evaluator base class and context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EvaluatorContext[InputsT, OutputT, MetadataT]:
    """Context passed to evaluators.

    Attributes:
        inputs: The input data that was passed to the task.
        output: The output produced by the task.
        expected_output: The expected output (if provided).
        metadata: Case metadata (if provided).
        duration: How long the task took to run (in seconds).

    """

    inputs: InputsT
    output: OutputT
    expected_output: OutputT | None
    metadata: MetadataT | None
    duration: float


@dataclass
class EvaluationReason:
    """Wraps an evaluation result with an optional reason.

    Attributes:
        value: The evaluation result (bool for assertion, float for score, str for label).
        reason: Optional explanation for the result.

    """

    value: bool | float | str
    reason: str | None = None


# Type alias for evaluator return types
EvaluatorOutput = (
    bool | float | str | EvaluationReason | dict[str, bool | float | str | EvaluationReason]
)


class Evaluator[InputsT, OutputT, MetadataT](ABC):
    """Base class for evaluators.

    Subclass this and implement the `evaluate` method to create custom evaluators.

    Return types:
        - bool: Recorded as an assertion (pass/fail)
        - float: Recorded as a score (0.0-1.0 recommended)
        - str: Recorded as a label
        - EvaluationReason: Any of the above with an explanation
        - dict: Multiple results with named keys
    """

    @property
    def name(self) -> str:
        """Name of the evaluator. Defaults to class name."""
        return self.__class__.__name__

    @abstractmethod
    async def evaluate(self, ctx: EvaluatorContext[InputsT, OutputT, MetadataT]) -> EvaluatorOutput:
        """Evaluate the task output.

        Args:
            ctx: The evaluation context containing inputs, output, expected, etc.

        Returns:
            bool, float, str, EvaluationReason, or dict of these.

        """
        ...
