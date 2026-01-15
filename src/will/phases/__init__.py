# src/will/phases/__init__.py
# ID: will.phases.init

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
