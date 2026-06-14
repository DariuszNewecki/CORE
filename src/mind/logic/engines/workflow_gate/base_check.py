# src/mind/logic/engines/workflow_gate/base_check.py

"""
Base class for workflow verification checks.

Each workflow check type (tests, coverage, linting, etc.) inherits from this
and implements its specific verification logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
# ID: f2323d9e-f30b-42d0-a429-121d261d7981
class StructuredViolation:
    """A per-file violation carrying structured occurrence data (ADR-098 D1/D2).

    Aggregate quality gates wrapping multi-issue external tools (mypy,
    pip-audit, pytest --collect-only) emit one of these per affected file
    instead of collapsing the whole tool run into a single string. The
    engine (``WorkflowGateEngine.verify_context``) recognizes this type and
    builds one ``AuditFinding`` per instance, preserving ``file_path`` and
    the structured ``context`` so the audit row-count matches reality and
    the renderer can surface the iceberg tail.

    Checks that do not wrap aggregate tools keep returning plain ``str``
    violations; both shapes coexist in a check's return list.
    """

    file_path: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


# ID: 7c327aab-023a-4f20-8856-7edf52864223
class WorkflowCheck(ABC):
    """
    Base class for workflow verification checks.

    Each subclass represents a specific quality gate (tests, coverage, linting, etc.)
    and implements the verification logic.
    """

    # Subclasses must define this
    check_type: str

    @abstractmethod
    # ID: 17d254ad-042e-4605-bd9e-f2913b32d974
    async def verify(
        self, file_path: Path | None, params: dict[str, Any]
    ) -> Sequence[str | StructuredViolation]:
        """
        Verify workflow requirements.

        Args:
            file_path: Optional specific file to check (None = context-level)
            params: Check-specific parameters

        Returns:
            A sequence of violations (empty = passed). Each element is either
            a plain ``str`` message (legacy/simple checks) or a
            ``StructuredViolation`` carrying per-file occurrence data for
            aggregate quality gates (ADR-098 D1/D2). The return type is a
            covariant ``Sequence`` so subclasses returning ``list[str]``
            remain valid overrides.
        """
        raise NotImplementedError
