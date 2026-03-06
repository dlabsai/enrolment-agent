"""Runner for evaluations with repeat support."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import logfire

from .dataset import Case, Dataset
from .evaluator import EvaluationReason, Evaluator, EvaluatorContext, EvaluatorOutput
from .report import EvaluationReport, EvaluationResult, ModelConfig, ReportCase, RunResult


def _process_evaluator_output(
    evaluator_name: str, output: EvaluatorOutput
) -> tuple[dict[str, EvaluationResult], dict[str, EvaluationResult], dict[str, EvaluationResult]]:
    """Process evaluator output into assertions, scores, and labels."""
    assertions: dict[str, EvaluationResult] = {}
    scores: dict[str, EvaluationResult] = {}
    labels: dict[str, EvaluationResult] = {}

    def process_single(
        name: str,
        value: bool | float | str | EvaluationReason,  # noqa: FBT001
    ) -> None:
        if isinstance(value, EvaluationReason):
            actual_value = value.value
            reason = value.reason
        else:
            actual_value = value
            reason = None

        result = EvaluationResult(name=name, value=actual_value, reason=reason)

        if isinstance(actual_value, bool):
            assertions[name] = result
        elif isinstance(actual_value, (int, float)):
            scores[name] = result
        elif isinstance(actual_value, str):
            labels[name] = result

    if isinstance(output, dict):
        for key, val in output.items():
            process_single(key, val)
    else:
        process_single(evaluator_name, output)

    return assertions, scores, labels


async def _run_single[InputsT, OutputT, MetadataT](
    case: Case[InputsT, OutputT, MetadataT],
    task: Callable[[InputsT], Awaitable[OutputT]],
    evaluators: list[Evaluator[InputsT, OutputT, MetadataT]],
    semaphore: asyncio.Semaphore,
    run_index: int = 0,
) -> RunResult[OutputT]:
    """Run a single case."""
    async with semaphore:
        with logfire.span(
            "eval_run {case_name} #{run_index}", case_name=case.name, run_index=run_index
        ):
            # Run the task
            start_time = time.perf_counter()
            try:
                output = await task(case.inputs)
                duration = time.perf_counter() - start_time
            except Exception as e:
                duration = time.perf_counter() - start_time
                logfire.error("Task error: {error}", error=str(e), case_name=case.name)
                return RunResult(output=None, duration=duration, error=str(e))

        # Create context for evaluators
        ctx = EvaluatorContext(
            inputs=case.inputs,
            output=output,
            expected_output=case.expected_output,
            metadata=case.metadata,
            duration=duration,
        )

        # Run evaluators
        all_assertions: dict[str, EvaluationResult] = {}
        all_scores: dict[str, EvaluationResult] = {}
        all_labels: dict[str, EvaluationResult] = {}

        for evaluator in evaluators:
            try:
                eval_output = await evaluator.evaluate(ctx)
                assertions, scores, labels = _process_evaluator_output(evaluator.name, eval_output)
                all_assertions.update(assertions)
                all_scores.update(scores)
                all_labels.update(labels)
            except Exception as e:
                # Record evaluator failure as a failed assertion
                logfire.error("Evaluator error: {error}", error=str(e), evaluator=evaluator.name)
                all_assertions[f"{evaluator.name}_error"] = EvaluationResult(
                    name=f"{evaluator.name}_error", value=False, reason=str(e)
                )

        # Log results
        passed = all(a.value for a in all_assertions.values()) if all_assertions else True
        logfire.info(
            "Run complete: {status}",
            status="PASSED" if passed else "FAILED",
            case_name=case.name,
            run_index=run_index,
            duration=duration,
            assertions={k: v.value for k, v in all_assertions.items()},
        )

        return RunResult(
            output=output,
            duration=duration,
            assertions=all_assertions,
            scores=all_scores,
            labels=all_labels,
        )


async def evaluate[InputsT, OutputT, MetadataT](
    dataset: Dataset[InputsT, OutputT, MetadataT],
    task: Callable[[InputsT], Awaitable[OutputT]],
    evaluators: list[Evaluator[InputsT, OutputT, MetadataT]],
    *,
    repeats: int = 1,
    max_concurrency: int = 10,
    models: dict[str, str] | None = None,
    model_configs: dict[str, ModelConfig] | None = None,
    additional_settings: dict[str, Any] | None = None,
) -> EvaluationReport[InputsT, OutputT, MetadataT]:
    """Run evaluation on a dataset with repeat and parallel execution support.

    All (cases x repeats) are run in parallel, limited by max_concurrency.

    Args:
        dataset: The dataset containing test cases.
        task: Async function that takes inputs and returns output.
        evaluators: List of evaluators to run on each result.
        repeats: Number of times to run each case (default: 1).
        max_concurrency: Maximum concurrent executions (default: 10).
            Set to 1 for sequential execution.
        models: Dictionary of model roles to model names used in evaluation (deprecated).
        model_configs: Dictionary of model roles to full model configurations.
        additional_settings: Dictionary of additional settings to display in the report.

    Returns:
        EvaluationReport with results and statistics.

    """
    total_runs = len(dataset.cases) * repeats

    with logfire.span(
        "Evaluation: {dataset_name}",
        dataset_name=dataset.name,
        total_cases=len(dataset.cases),
        repeats=repeats,
        total_runs=total_runs,
        max_concurrency=max_concurrency,
    ):
        semaphore = asyncio.Semaphore(max_concurrency)

        # Create all tasks: each case x repeats
        tasks: list[tuple[Case[InputsT, OutputT, MetadataT], asyncio.Task[RunResult[OutputT]]]] = []
        for case in dataset.cases:
            for run_idx in range(repeats):
                coro = _run_single(case, task, evaluators, semaphore, run_idx + 1)
                tasks.append((case, asyncio.create_task(coro)))

        # Wait for all tasks
        await asyncio.gather(*[t for _, t in tasks])

        # Group results by case
        results_by_case: dict[str, list[RunResult[OutputT]]] = {}
        for case, task_obj in tasks:
            results_by_case.setdefault(case.name, []).append(task_obj.result())

        # Build report
        report_cases: list[ReportCase[InputsT, OutputT, MetadataT]] = []
        for case in dataset.cases:
            run_results = results_by_case.get(case.name, [])
            report_case = ReportCase(
                name=case.name,
                inputs=case.inputs,
                expected_output=case.expected_output,
                metadata=case.metadata,
                run_results=run_results,
            )
            report_case.compute_stats()
            report_cases.append(report_case)

        report = EvaluationReport(
            name=dataset.name,
            cases=report_cases,
            repeats=repeats,
            max_concurrency=max_concurrency,
            models=models or {},
            model_configs=model_configs or {},
            additional_settings=additional_settings or {},
        )

        # Log summary
        passed_cases = sum(
            1
            for c in report.cases
            if c.stats and all(rate == 1.0 for rate in c.stats.assertion_pass_rates.values())
        )
        logfire.info(
            "Evaluation complete: {passed}/{total} cases passed",
            passed=passed_cases,
            total=len(report.cases),
            dataset_name=dataset.name,
        )

        return report
