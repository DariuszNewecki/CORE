# src/body/actions/base.py
"""
Defines the base interface for all executable actions in the CORE system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from shared.models import TaskParams
    from will.agents.plan_executor import PlanExecutorContext


# ID: 1eaf9a8d-7b6c-4f5a-8b3e-9c7d6e5f4a3b
class ActionHandler(ABC):
    """Abstract base class for a specialist that handles a single action."""

    @property
    @abstractmethod
    # ID: 3b8a13fc-9c44-4829-9613-909640d3e733
    def name(self) -> str:
        """The unique name of the action, e.g., 'read_file'."""
        pass

    @abstractmethod
    # ID: 1780136a-31ee-4db1-bbf8-04c0110b4cca
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """
        Executes the action.

        Args:
            params: The parameters for this specific task.
            context: The shared execution context, allowing access to file content,
                     the file handler, git service, etc.
        """
        pass
