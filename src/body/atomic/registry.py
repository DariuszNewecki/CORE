# src/body/atomic/registry.py
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
from dataclasses import dataclass, field
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
    STATE = "state"  # State machine transitions


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
    - Which audit check_ids it can remediate (remediates)
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

    remediates: list[str] = field(default_factory=list)
    """
    Audit check IDs this action can autonomously remediate.

    ViolationRemediatorWorker uses this to map Blackboard findings
    to actions without any static YAML mapping.

    Example: ["purity.stable_id_anchor", "linkage.assign_ids"]
    """


# ID: 7f4b2c8e-9d3a-4e1f-8c7d-5a2b3c4d5e6f
class ActionRegistry:
    """
    Global registry of all atomic actions in CORE.

    Actions are registered at module load time and can be:
    - Executed individually via CLI
    - Composed into workflows
    - Validated against constitutional policies
    - Audited for compliance
    - Looked up by the check_ids they remediate
    """

    def __init__(self):
        self._actions: dict[str, ActionDefinition] = {}
        # Reverse index: check_id -> action_id for O(1) remediation lookup
        self._remediates_index: dict[str, str] = {}

    # ID: 2a3b4c5d-6e7f-8a9b-0c1d-2e3f4a5b6c7d
    def register(self, definition: ActionDefinition) -> None:
        """Register an action definition."""
        if definition.action_id in self._actions:
            raise ValueError(f"Action already registered: {definition.action_id}")
        self._actions[definition.action_id] = definition

        # Build reverse index for remediation lookup
        for check_id in definition.remediates:
            if check_id in self._remediates_index:
                logger.warning(
                    "check_id '%s' already claimed by action '%s', "
                    "skipping claim by '%s'",
                    check_id,
                    self._remediates_index[check_id],
                    definition.action_id,
                )
            else:
                self._remediates_index[check_id] = definition.action_id

    # ID: 3b4c5d6e-7f8a-9b0c-1d2e-3f4a5b6c7d8e
    def get(self, action_id: str) -> ActionDefinition | None:
        """Get action definition by ID."""
        return self._actions.get(action_id)

    # ID: 8a9b0c1d-2e3f-4a5b-6c7d-8e9f0a1b2c3d
    def get_by_check_id(self, check_id: str) -> ActionDefinition | None:
        """
        Look up the action that remediates the given audit check_id.

        Used by ViolationRemediatorWorker to map Blackboard findings
        directly to executable actions — no static YAML required.

        Returns None if no registered action claims this check_id.
        """
        action_id = self._remediates_index.get(check_id)
        if not action_id:
            return None
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

    sig = inspect.signature(func)
    return_annotation = sig.return_annotation

    if return_annotation is inspect.Signature.empty:
        raise TypeError(
            f"Constitutional violation in '{func_name}': "
            f"Missing return type annotation. "
            f"Rule: atomic_actions.must_return_action_result. "
            f"Required: '-> ActionResult'"
        )

    is_action_result = False

    if return_annotation is ActionResult:
        is_action_result = True
    elif isinstance(return_annotation, str):
        if return_annotation == "ActionResult":
            is_action_result = True
    elif hasattr(return_annotation, "__name__"):
        if return_annotation.__name__ == "ActionResult":
            is_action_result = True

    if not is_action_result:
        raise TypeError(
            f"Constitutional violation in '{func_name}': "
            f"Return type must be 'ActionResult', got '{return_annotation}'. "
            f"Rule: atomic_actions.must_return_action_result. "
            f"Tuple returns like (bool, str) are explicitly forbidden."
        )

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
    remediates: list[str] | None = None,
):
    """
    Decorator to register an action with constitutional enforcement.

    CONSTITUTIONAL ENFORCEMENT:
    This decorator enforces .intent/rules/architecture/atomic_actions.json at
    module import time. Functions that violate constitutional rules will cause
    the module import to fail with a TypeError.

    Args:
        remediates: List of audit check_ids this action can fix autonomously.
                    ViolationRemediatorWorker uses this to close the audit loop
                    without any static YAML mapping. Example:
                    remediates=["purity.stable_id_anchor", "linkage.assign_ids"]
    """

    # ID: 5352e0e1-0d42-40e8-8ccb-7437a5c5fa18
    def decorator(func: Callable[..., Awaitable[ActionResult]]):
        try:
            _validate_action_signature(func)
        except TypeError as e:
            raise TypeError(f"Cannot register action '{action_id}': {e}") from e

        definition = ActionDefinition(
            action_id=action_id,
            description=description,
            category=category,
            policies=policies,
            impact_level=impact_level,
            executor=func,
            requires_db=requires_db,
            requires_vectors=requires_vectors,
            remediates=remediates or [],
        )
        action_registry.register(definition)

        logger.info(
            "Action '%s' registered successfully with constitutional compliance",
            action_id,
        )

        return func

    return decorator
