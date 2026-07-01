# src/will/agents/acceptance/__init__.py
"""
AcceptanceCondition protocol and implementations (ADR-135 D3).

Three concrete conditions are provided:
  IntentGuardAcceptanceCondition — validates generated code via IntentGuard
                                   (AST-based; available in-process).
  PytestAcceptanceCondition      — runs pytest via test.sandbox_validate action;
                                   requires ActionExecutor injection.
  CompositeAcceptanceCondition   — AND of multiple conditions; returns the first
                                   failing condition's violation_summary.

These are Will-tier primitives used by IterativeCoderAgent. They do NOT use
subprocess directly (governance.dangerous_execution_primitives; Will MUST NOT
use subprocess). I/O-bound conditions delegate to Body actions via ActionExecutor.
"""

from __future__ import annotations

from .conditions import (
    AcceptanceCondition,
    AcceptanceResult,
    CompositeAcceptanceCondition,
    IntentGuardAcceptanceCondition,
    PytestAcceptanceCondition,
)


__all__ = [
    "AcceptanceCondition",
    "AcceptanceResult",
    "CompositeAcceptanceCondition",
    "IntentGuardAcceptanceCondition",
    "PytestAcceptanceCondition",
]
