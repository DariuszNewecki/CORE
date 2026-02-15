# src/shared/protocols/executor.py
# ID: 0808bda4-c3bd-450a-ad06-0b2324339baa

"""
Action Executor Protocol - The Universal Mutation Contract.

This protocol defines the "shape" of the component responsible for
executing atomic actions. It allows the Will layer (Agents) to
request system changes without depending on the Body layer's
implementation details.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from shared.action_types import ActionResult


@runtime_checkable
# ID: 9b980986-296c-4156-8818-0ccd98a38254
class ActionExecutorProtocol(Protocol):
    """
    Structural interface for the universal action execution gateway.

    Any class that implements this 'execute' method can be used by
    CORE agents to perform governed mutations.
    """

    # ID: a0e7d2d1-1961-4024-ab89-55508e815ec2
    async def execute(
        self,
        action_id: str,
        write: bool = False,
        **params: Any,
    ) -> ActionResult:
        """
        Execute an action with full constitutional governance.

        Args:
            action_id: Registered action ID (e.g., "fix.format")
            write: Whether to apply changes (False = dry-run)
            **params: Action-specific parameters

        Returns:
            ActionResult with execution details and status
        """
        ...
