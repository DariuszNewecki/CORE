# src/mind/logic/engines/workflow_gate/base_check.py

"""
Base class for workflow verification checks.

Each workflow check type (tests, coverage, linting, etc.) inherits from this
and implements its specific verification logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


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
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify workflow requirements.

        Args:
            file_path: Optional specific file to check (None = context-level)
            params: Check-specific parameters

        Returns:
            List of violation messages (empty = passed)
        """
        raise NotImplementedError
