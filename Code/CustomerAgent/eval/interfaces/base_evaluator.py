"""
Abstract base interfaces for evaluation frameworks.

This module defines the common interface that all evaluation frameworks
should implement to ensure consistency across different platforms.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum


class EvaluationStatus(Enum):
    """Status of an evaluation result"""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class EvaluationResult:
    """Standard evaluation result format across all frameworks"""
    metric_name: str
    score: Optional[float]
    threshold: Optional[float]
    status: EvaluationStatus
    success: bool
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        """Check if the evaluation passed"""
        return self.status == EvaluationStatus.PASS and self.success


@dataclass
class EvaluationInput:
    """Standard input format for evaluations"""
    input_text: str
    actual_output: str
    context: Optional[List[str]] = None
    expected_output: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseEvaluator(ABC):
    """
    Abstract base class for all evaluation frameworks.
    
    Each evaluation framework (DeepEval, LangSmith, etc.) should inherit
    from this class and implement the required methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def get_available_metrics(self) -> List[str]:
        """Return list of available metrics for this framework"""
        pass
    
    @abstractmethod
    def configure_metric(self, metric_name: str, threshold: float, **kwargs) -> bool:
        """Configure a specific metric with threshold and options"""
        pass
    
    @abstractmethod
    def run_evaluation(
        self, 
        evaluation_input: EvaluationInput,
        selected_metrics: Dict[str, float],
        **kwargs
    ) -> List[EvaluationResult]:
        """Run evaluation with selected metrics and return standardized results"""
        pass
    
    @abstractmethod
    def supports_cloud_streaming(self) -> bool:
        """Check if this framework supports cloud streaming/tracking"""
        pass
    
    def validate_input(self, evaluation_input: EvaluationInput) -> bool:
        """Validate evaluation input (can be overridden by subclasses)"""
        return (
            evaluation_input.input_text is not None and
            evaluation_input.actual_output is not None
        )
    
    def get_framework_info(self) -> Dict[str, str]:
        """Get information about this evaluation framework"""
        return {
            "name": self.name,
            "version": getattr(self, "version", "unknown"),
            "supports_cloud": str(self.supports_cloud_streaming()),
            "available_metrics": str(len(self.get_available_metrics()))
        }