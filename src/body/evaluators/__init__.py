# src/body/evaluators/__init__.py

"""
Evaluators - Audit phase components.

Evaluators assess quality, identify patterns, and provide recommendations.
They evaluate results and return structured assessments.

Available Evaluators:
- FailureEvaluator: Analyze test failure patterns and recommend actions

Constitutional Alignment:
- Phase: AUDIT (evaluation, no execution)
- Returns recommendations (not decisions)
- Tracks patterns for learning

Usage:
    from body.evaluators import FailureEvaluator

    evaluator = FailureEvaluator()
    result = await evaluator.execute(
        error="TypeError: ...",
        pattern_history=[]
    )

    if result.data['should_switch']:
        # Take action based on recommendation
        pass
"""

from __future__ import annotations

from .failure_evaluator import FailureEvaluator


__all__ = [
    "FailureEvaluator",
]
