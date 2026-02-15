# src/body/atomic/registry.py
# ID: f04360ba-957e-456e-99ab-8bf7bc05da54
"""
Atomic Actions Registry - Constitutional Action Definitions

Every action in CORE is:
1. Independently executable
2. Constitutionally governed
3. Returns ActionResult
4. Composable into workflows
5. Auditable and traceable

UNIX Philosophy: Each action does ONE thing well.

CONSTITUTIONAL ENFORCEMENT:
This module enforces .intent/rules/architecture/atomic_actions.json at registration time.
Actions that violate constitutional rules CANNOT be registered.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

from shared.action_types import ActionResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 6166d4ed-db63-4363-95c3-504ef1b9a3e0
class ActionCategory(str, Enum):
    """Constitutional action categories."""

    FIX = "fix"  # Code remediation
    SYNC = "sync"  # State synchronization
    CHECK = "check"  # Validation/audit
    BUILD = "build"  # Construction


@dataclass
# ID: 89f5c3e2-1a47-4c8d-9e57-2c6e4a8f3b1d
class ActionDefinition:
    """
    Constitutional metadata for an atomic action.

    Every action must declare:
    - What it does (description)
    - What policies govern it (policies)
    - What category it belongs to (category)
    - What impact level it has (impact_level)
    """

    action_id: str
    """Unique action identifier (e.g., 'fix.format', 'sync.db')"""

    description: str
    """Human-readable description of what this action does"""

    category: ActionCategory
    """Constitutional category"""

    policies: list[str]
    """Policy IDs that govern this action"""

    impact_level: str
    """Impact level: 'safe', 'moderate', 'dangerous'"""

    executor: Callable[..., Awaitable[ActionResult]]
    """Async function that executes the action"""

    requires_db: bool = False
    """Whether this action requires database access"""

    requires_vectors: bool = False
    """Whether this action requires vector store access"""


# ID: 7f4b2c8e-9d3a-4e1f-8c7d-5a2b3c4d5e6f
class ActionRegistry:
    """
    Global registry of all atomic actions in CORE.

    Actions are registered at module load time and can be:
    - Executed individually via CLI
    - Composed into workflows
    - Validated against constitutional policies
    - Audited for compliance
    """

    def __init__(self):
        self._actions: dict[str, ActionDefinition] = {}

    # ID: 2a3b4c5d-6e7f-8a9b-0c1d-2e3f4a5b6c7d
    def register(self, definition: ActionDefinition) -> None:
        """Register an action definition."""
        if definition.action_id in self._actions:
            raise ValueError(f"Action already registered: {definition.action_id}")
        self._actions[definition.action_id] = definition

    # ID: 3b4c5d6e-7f8a-9b0c-1d2e-3f4a5b6c7d8e
    def get(self, action_id: str) -> ActionDefinition | None:
        """Get action definition by ID."""
        return self._actions.get(action_id)

    # ID: 4c5d6e7f-8a9b-0c1d-2e3f-4a5b6c7d8e9f
    def get_by_category(self, category: ActionCategory) -> list[ActionDefinition]:
        """Get all actions in a category."""
        return [a for a in self._actions.values() if a.category == category]

    # ID: 5d6e7f8a-9b0c-1d2e-3f4a-5b6c7d8e9f0a
    def list_all(self) -> list[ActionDefinition]:
        """List all registered actions."""
        return list(self._actions.values())


# Global singleton registry
action_registry = ActionRegistry()


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
def _validate_action_signature(func: Callable[..., Awaitable[ActionResult]]) -> None:
    """
    Validate function signature against constitutional requirements.

    Enforces .intent/rules/architecture/atomic_actions.json:
    - atomic_actions.must_return_action_result
    - atomic_actions.must_have_decorator
    - atomic_actions.no_governance_bypass

    Raises:
        TypeError: If function signature violates constitutional rules
    """
    func_name = func.__name__

    # Rule: atomic_actions.must_return_action_result
    # Check return type annotation directly from signature
    # This avoids issues with TYPE_CHECKING imports
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation

    if return_annotation is inspect.Signature.empty:
        raise TypeError(
            f"Constitutional violation in '{func_name}': "
            f"Missing return type annotation. "
            f"Rule: atomic_actions.must_return_action_result. "
            f"Required: '-> ActionResult'"
        )

    # Check if return annotation is ActionResult
    # Handle string annotations (from __future__ import annotations)
    is_action_result = False

    if return_annotation is ActionResult:
        is_action_result = True
    elif isinstance(return_annotation, str):
        # Forward reference as string
        if return_annotation == "ActionResult":
            is_action_result = True
    elif hasattr(return_annotation, "__name__"):
        # Check class name
        if return_annotation.__name__ == "ActionResult":
            is_action_result = True

    if not is_action_result:
        raise TypeError(
            f"Constitutional violation in '{func_name}': "
            f"Return type must be 'ActionResult', got '{return_annotation}'. "
            f"Rule: atomic_actions.must_return_action_result. "
            f"Tuple returns like (bool, str) are explicitly forbidden."
        )

    # Rule: atomic_actions.must_have_decorator
    # Check if function has @atomic_action decorator
    # The decorator sets _atomic_action_metadata attribute
    has_atomic_decorator = hasattr(func, "_atomic_action_metadata")

    if not has_atomic_decorator:
        raise TypeError(
            f"Constitutional violation in '{func_name}': "
            f"Missing @atomic_action decorator. "
            f"Rule: atomic_actions.must_have_decorator. "
            f"Required: @atomic_action(action_id=..., intent=..., impact=..., policies=[...])"
        )

    logger.debug(
        "Constitutional validation passed for action '%s': "
        "return type=ActionResult, has @atomic_action decorator",
        func_name,
    )


# ID: 6e7f8a9b-0c1d-2e3f-4a5b-6c7d8e9f0a1b
def register_action(
    action_id: str,
    description: str,
    category: ActionCategory,
    policies: list[str],
    impact_level: str = "safe",
    requires_db: bool = False,
    requires_vectors: bool = False,
):
    """
    Decorator to register an action with constitutional enforcement.

    CONSTITUTIONAL ENFORCEMENT:
    This decorator enforces .intent/rules/architecture/atomic_actions.json at
    module import time. Functions that violate constitutional rules will cause
    the module import to fail with a TypeError.

    Enforced rules:
    - atomic_actions.must_return_action_result: Return type must be ActionResult
    - atomic_actions.must_have_decorator: Must have @atomic_action decorator
    - atomic_actions.no_governance_bypass: No tuple returns allowed

    Usage:
        @register_action(
            action_id="fix.format",
            description="Format code with Black and Ruff",
            category=ActionCategory.FIX,
            policies=["code_quality_standards"],
        )
        @atomic_action(
            action_id="fix.format",
            intent="Ensure code style compliance",
            impact=ActionImpact.WRITE_CODE,
            policies=["atomic_actions"],
        )
        async def format_code(write: bool = False) -> ActionResult:
            ...
    """

    # ID: 5352e0e1-0d42-40e8-8ccb-7437a5c5fa18
    def decorator(func: Callable[..., Awaitable[ActionResult]]):
        # CONSTITUTIONAL ENFORCEMENT GATE
        # Validate function signature before registration
        try:
            _validate_action_signature(func)
        except TypeError as e:
            # Re-raise with action_id context
            raise TypeError(f"Cannot register action '{action_id}': {e}") from e

        # If validation passes, proceed with registration
        definition = ActionDefinition(
            action_id=action_id,
            description=description,
            category=category,
            policies=policies,
            impact_level=impact_level,
            executor=func,
            requires_db=requires_db,
            requires_vectors=requires_vectors,
        )
        action_registry.register(definition)

        logger.info(
            "Action '%s' registered successfully with constitutional compliance",
            action_id,
        )

        return func

    return decorator
