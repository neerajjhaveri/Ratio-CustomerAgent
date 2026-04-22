"""
Interfaces and abstract classes for evaluation frameworks.
"""

from .base_evaluator import BaseEvaluator, EvaluationResult, EvaluationInput, EvaluationStatus

__all__ = [
    "BaseEvaluator",
    "EvaluationResult", 
    "EvaluationInput",
    "EvaluationStatus"
]