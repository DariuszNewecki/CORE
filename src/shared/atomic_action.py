# src/shared/atomic_action.py
"""
Atomic action decorator and metadata system.

Provides the @atomic_action decorator that marks functions as constitutional
atomic actions, attaching metadata that enables governance, composition,
and autonomous orchestration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from shared.action_types import ActionImpact
from shared.logger import getLogger


logger = getLogger(__name__)


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

    Examples:
    - "symbol_identification": Requires stable UUIDs on symbols
    - "import_organization": Enforces PEP 8 import grouping
    - "gdpr_compliance": Ensures PII handling follows GDPR

    The constitutional framework validates that:
    1. All referenced policies exist
    2. Action's behavior complies with policies
    3. Output doesn't violate any policy constraints
    """

    category: str | None = None
    """
    Optional logical grouping for organization.

    Common categories:
    - "fixers": Actions that repair code
    - "checks": Actions that validate code
    - "generators": Actions that create new code
    - "sync": Actions that synchronize data
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

    Usage:
        @atomic_action(
            action_id="fix.ids",
            intent="Assign stable UUIDs to untagged public symbols",
            impact=ActionImpact.WRITE_METADATA,
            policies=["symbol_identification"],
            category="fixers",
        )
        async def fix_ids_internal(write: bool) -> ActionResult:
            # Implementation...
            return ActionResult(...)

    The decorated function becomes part of CORE's constitutional framework:
    - Its metadata is used for governance
    - It can be composed into workflows
    - It can be called by autonomous agents (within policy bounds)

    Args:
        action_id: Unique identifier (dot notation recommended)
        intent: Human-readable description
        impact: What kind of changes this action makes
        policies: List of policy IDs that govern this action
        category: Optional grouping for organization

    Returns:
        Decorator function that wraps the target function
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

            Future enhancements:
            - Pre-execution validation (check policies exist, permissions OK)
            - Post-execution validation (verify result structure, check compliance)
            - Performance monitoring and logging
            - Automatic retry on transient failures
            - Constitutional audit trail
            """

            # TODO: Pre-execution governance hooks
            # - Validate metadata.policies exist
            # - Check caller has permission for this action
            # - Verify action authorized for current context

            # Execute the action
            result = await func(*args, **kwargs)

            # TODO: Post-execution governance hooks
            # - Validate result structure (is it an ActionResult?)
            # - Check result.data against policy constraints
            # - Log to constitutional audit trail
            # - Detect and report policy violations

            return result

        return wrapper

    return decorator


# ID: 9e59eb43-1535-460e-a96f-f47da30c7d3a
def get_action_metadata(func: Callable) -> ActionMetadata | None:
    """
    Extract ActionMetadata from a decorated function.

    This enables introspection and discovery of atomic actions:
    - Workflow planners can find available actions
    - Governance systems can validate action usage
    - Documentation generators can auto-document actions

    Args:
        func: Function that may have been decorated with @atomic_action

    Returns:
        ActionMetadata if function is decorated, None otherwise

    Example:
        metadata = get_action_metadata(fix_ids_internal)
        if metadata:
            logger.info(f"Action: {metadata.action_id}")
            logger.info(f"Intent: {metadata.intent}")
            logger.info(f"Policies: {metadata.policies}")
    """
    return getattr(func, "_atomic_action_metadata", None)
