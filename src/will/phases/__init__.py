# src/will/phases/__init__.py
# ID: 8280aa68-f535-46ac-90a1-3dd2c4651872

"""
Phase Implementations for Constitutional Workflows

Each phase is a focused unit that:
- Takes WorkflowContext as input
- Produces PhaseResult as output
- Has clear constitutional requirements
- Is independently testable
"""

from __future__ import annotations


__all__ = [
    "CanaryValidationPhase",
    "CodeGenerationPhase",
    "ExecutionPhase",
    "PlanningPhase",
    "SandboxValidationPhase",
    "StyleCheckPhase",
    "TestGenerationPhase",
]
