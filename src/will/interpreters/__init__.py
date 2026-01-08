# src/will/interpreters/__init__.py

"""
Interpreters - INTERPRET phase components.

Interpreters convert heterogeneous inputs (natural language, CLI args, API requests)
into canonical TaskStructure that can be routed to appropriate workflows.

This is the universal entry point for all CORE operations:
    INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE

Available Interpreters:
- NaturalLanguageInterpreter: "refactor this file" → TaskStructure
- CLIArgsInterpreter: Typer args → TaskStructure
- RequestInterpreter: Base class for custom interpreters

Constitutional Alignment:
- Phase: INTERPRET (new in v2.2.0)
- No side effects (pure parsing)
- Returns structured ComponentResult
- Confidence scoring for workflow routing

Usage:
    from will.interpreters import NaturalLanguageInterpreter

    interpreter = NaturalLanguageInterpreter()
    result = await interpreter.execute(user_message="refactor UserService for clarity")
    task = result.data["task"]  # TaskStructure
"""

from __future__ import annotations

from .request_interpreter import (
    CLIArgsInterpreter,
    NaturalLanguageInterpreter,
    RequestInterpreter,
    TaskStructure,
    TaskType,
)


__all__ = [
    "CLIArgsInterpreter",
    "NaturalLanguageInterpreter",
    "RequestInterpreter",
    "TaskStructure",
    "TaskType",
]
