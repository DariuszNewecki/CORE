# src/body/flows/__init__.py
"""
Constitutional Flow layer — composition primitives between AtomicActions and Workers.

Flows are declared in .intent/flows/*.yaml and loaded by FlowRegistry at
first access. No Flow is hardcoded here.

Constitutional alignment: CORE-Flow.md

Hierarchy:
    AtomicAction  — does exactly one thing
          ↓ composes into
    Flow          — named, ordered sequence of AtomicActions or Flows
          ↓ invoked by
    Worker        — constitutional officer that decides when and why
"""

from __future__ import annotations

from body.flows.executor import FlowExecutor
from body.flows.registry import FlowDefinition, FlowStep, StepKind, flow_registry
from body.flows.result import FlowResult, StepResult


__all__ = [
    "FlowDefinition",
    "FlowExecutor",
    "FlowResult",
    "FlowStep",
    "StepKind",
    "StepResult",
    "flow_registry",
]
