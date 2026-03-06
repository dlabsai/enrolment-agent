"""Evaluation library with repeat and parallel execution support."""

from .dataset import Case, Dataset
from .evaluator import EvaluationReason, Evaluator, EvaluatorContext
from .report import EvaluationReport, ModelConfig, ReportCase, ReportCaseStats
from .runner import evaluate

__all__ = [
    "Case",
    "Dataset",
    "EvaluationReason",
    "EvaluationReport",
    "Evaluator",
    "EvaluatorContext",
    "ModelConfig",
    "ReportCase",
    "ReportCaseStats",
    "evaluate",
]
