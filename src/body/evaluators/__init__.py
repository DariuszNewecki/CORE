# src/body/evaluators/__init__.py

"""
Body Evaluators - AUDIT Phase Components

Evaluators assess quality, identify patterns, and provide recommendations.
They evaluate results and return structured assessments.

Available Evaluators:
- AtomicActionsEvaluator: Atomic action pattern compliance
- ClarityEvaluator: Code complexity analysis
- ConstitutionalEvaluator: Constitutional compliance checking
- FailureEvaluator: Test failure pattern recognition
- PatternEvaluator: Design pattern compliance
- PerformanceEvaluator: Performance metrics assessment
- SecurityEvaluator: Security vulnerability detection

Constitutional Alignment:
- Phase: AUDIT (evaluation, no execution)
- Returns recommendations (not decisions)
- Tracks patterns for learning
"""

from __future__ import annotations

from .atomic_actions_evaluator import (
    AtomicActionsEvaluator,
    AtomicActionViolation,
    format_atomic_action_violations,
)
from .clarity_evaluator import ClarityEvaluator
from .constitutional_evaluator import ConstitutionalEvaluator
from .failure_evaluator import FailureEvaluator
from .pattern_evaluator import (
    PatternEvaluator,
    format_violations,
    load_patterns_dict,
)
from .performance_evaluator import PerformanceEvaluator
from .security_evaluator import SecurityEvaluator


__all__ = [
    "AtomicActionViolation",
    "AtomicActionsEvaluator",
    "ClarityEvaluator",
    "ConstitutionalEvaluator",
    "FailureEvaluator",
    "PatternEvaluator",
    "PerformanceEvaluator",
    "SecurityEvaluator",
    "format_atomic_action_violations",
    "format_violations",
    "load_patterns_dict",
]
