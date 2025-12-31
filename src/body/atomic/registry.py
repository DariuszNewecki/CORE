# src/body/atomic/registry.py
# ID: actions.registry
"""
Atomic Actions Registry - Constitutional Action Definitions

Every action in CORE is:
1. Independently executable
2. Constitutionally governed
3. Returns ActionResult
4. Composable into workflows
5. Auditable and traceable

UNIX Philosophy: Each action does ONE thing well.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

from shared.action_types import ActionResult


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
    Decorator to register an action.

    Usage:
        @register_action(
            action_id="fix.format",
            description="Format code with Black and Ruff",
            category=ActionCategory.FIX,
            policies=["code_quality_standards"],
        )
        async def format_code(write: bool = False) -> ActionResult:
            ...
    """

    # ID: 5352e0e1-0d42-40e8-8ccb-7437a5c5fa18
    def decorator(func: Callable[..., Awaitable[ActionResult]]):
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
        return func

    return decorator
