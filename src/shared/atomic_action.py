# src/shared/atomic_action.py
"""
Atomic action decorator and metadata system.

Provides the @atomic_action decorator that marks functions as constitutional
atomic actions, attaching metadata that enables governance, composition,
and autonomous orchestration.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from shared.action_types import ActionImpact

# NEW IMPORT: Governance token verification
from shared.governance_token import verify_authorization


@dataclass(frozen=True)
# ID: 4ea79530-a6b0-478a-ae7f-0ac9ca69ead2
class ActionMetadata:
    """
    Constitutional metadata about an atomic action.
    """

    action_id: str
    intent: str
    impact: ActionImpact
    policies: list[str]
    category: str | None = None


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
            # --- SECURITY UPDATE P1.1 ---
            # Verify the caller has the ID Badge (Governance Token)
            verify_authorization(action_id)
            # ----------------------------

            # Use standard logging to avoid circular import during bootstrap.
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
    """
    return getattr(func, "_atomic_action_metadata", None)
