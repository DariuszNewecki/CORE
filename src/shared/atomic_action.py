# src/shared/atomic_action.py
"""
Atomic action decorator and metadata system.

Provides the @atomic_action decorator that marks functions as constitutional
atomic actions, attaching metadata that enables governance, composition,
and autonomous orchestration.
"""

from __future__ import annotations

import logging  # CONSTITUTIONAL FIX: Use stdlib logging to break circular import with shared.logger
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from shared.action_types import ActionImpact


@dataclass(frozen=True)
# ID: 4ea79530-a6b0-478a-ae7f-0ac9ca69ead2
class ActionMetadata:
    """
    Constitutional metadata about an atomic action.

    This is the Mind-layer definition of an action—what it does, what it
    affects, and what policies govern it. The constitution uses this metadata
    to validate actions before and after execution.

    Attributes:
        action_id: Unique identifier (e.g., "fix.ids", "check.imports")
        intent: Human-readable description of action's purpose
        impact: What kind of changes the action makes
        policies: List of constitutional policy IDs that apply
        category: Optional logical grouping (e.g., "fixers", "checks")
    """

    action_id: str
    """Unique identifier for this action"""

    intent: str
    """Human-readable description of what this action does"""

    impact: ActionImpact
    """Classification of changes this action makes"""

    policies: list[str]
    """
    Constitutional policy IDs that govern this action.
    """

    category: str | None = None
    """
    Optional logical grouping for organization.
    """


# ID: 6f253053-3ba2-46e9-8921-1cf4f4f44f86
def atomic_action(
    action_id: str,
    intent: str,
    impact: ActionImpact,
    policies: list[str],
    category: str | None = None,
) -> Callable[[Callable], Callable]:
    """
    Decorator that marks a function as a constitutional atomic action.

    This decorator:
    1. Attaches ActionMetadata to the function
    2. Provides hooks for future governance features
    3. Enables the function to be discovered and orchestrated
    """

    metadata = ActionMetadata(
        action_id=action_id,
        intent=intent,
        impact=impact,
        policies=policies,
        category=category,
    )

    # ID: 3578222b-00ae-4cde-9865-e3db946a9c4e
    def decorator(func: Callable) -> Callable:
        """Actual decorator that wraps the function."""

        # Attach metadata to function for introspection
        func._atomic_action_metadata = metadata  # type: ignore

        @wraps(func)
        # ID: 1e4475b4-da11-44d9-bf61-a06feee816ee
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """
            Wrapper that provides hooks for future governance features.
            """
            # Use standard logging to avoid circular import during bootstrap.
            # This will still use the handlers configured in shared.logger.
            logger = logging.getLogger(func.__module__)
            logger.debug("Executing atomic action: %s", action_id)

            # Execute the action
            result = await func(*args, **kwargs)

            return result

        return wrapper

    return decorator


# ID: 9e59eb43-1535-460e-a96f-f47da30c7d3a
def get_action_metadata(func: Callable) -> ActionMetadata | None:
    """
    Extract ActionMetadata from a decorated function.

    This enables introspection and discovery of atomic actions.
    """
    return getattr(func, "_atomic_action_metadata", None)
