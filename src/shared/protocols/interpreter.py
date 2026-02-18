# src/shared/protocols/interpreter.py

"""
Protocol defining the shape of Task Structures.

Allows Mind layer to reason about intent without importing Will.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
# ID: 4dd18afc-de7e-4703-abf8-d815ce21c874
class TaskStructureProtocol(Protocol):
    """The formal blueprint for a parsed user task."""

    task_type: Any
    intent: str
    targets: list[str]
    constraints: dict[str, Any]
    context: dict[str, Any]
    confidence: float
