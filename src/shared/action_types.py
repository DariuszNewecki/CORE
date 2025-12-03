# src/shared/action_types.py
"""
Universal action result types for CORE's atomic action framework.

This module defines the foundational types that unify all operations in CORE,
replacing the separate CommandResult and AuditCheckResult with a single,
universal contract that enables constitutional governance across all domains.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ID: 29ed0df5-f34f-4af8-81f1-49207bd75e6e
class ActionImpact(Enum):
    """
    Classification of an action's impact on system state.

    This helps the constitutional framework understand what kind of changes
    an action will make, enabling appropriate validation and governance.
    """

    READ_ONLY = "read-only"
    """Action only reads data, makes no changes"""

    WRITE_METADATA = "write-metadata"
    """Action writes metadata (IDs, tags, comments) but not functional code"""

    WRITE_CODE = "write-code"
    """Action writes or modifies functional code"""

    WRITE_DATA = "write-data"
    """Action writes to databases, files, or external systems"""


@dataclass
# ID: 9c64e67a-8078-4c5b-b8c3-d9d0735fd883
class ActionResult:
    """
    Universal result contract for all atomic actions in CORE.

    This replaces both CommandResult (for commands) and AuditCheckResult (for checks)
    with a single abstraction that enables:
    - Universal governance (same validation for all actions)
    - Composable workflows (actions return compatible results)
    - Constitutional compliance (structured data for policy enforcement)
    - Machine-readable outcomes (enables autonomous decision-making)

    Every operation in CORE—whether checking code, generating documentation,
    or building systems—returns an ActionResult.
    """

    action_id: str
    """
    Unique identifier for this action (e.g., 'fix.ids', 'check.imports').

    Convention: Use dot notation with category prefix:
    - fix.*: Code fixing actions
    - check.*: Validation actions
    - generate.*: Code generation actions
    - sync.*: Data synchronization actions
    """

    ok: bool
    """
    Binary success indicator.

    True: Action completed successfully
    False: Action failed or found violations

    For checks: False means violations found
    For fixes: False means couldn't complete the fix
    For generation: False means couldn't generate valid output
    """

    data: dict[str, Any]
    """
    Action-specific structured results.

    This is the flexible payload where each action type can store its
    specific outcomes. Common patterns:

    For checks:
        {"violations_count": int, "violations": list[dict], "files_scanned": int}

    For fixes:
        {"items_fixed": int, "items_failed": int, "dry_run": bool}

    For generation:
        {"files_created": list[str], "lines_of_code": int}

    Constitutional validation can inspect this data to ensure actions
    are operating within policy bounds.
    """

    duration_sec: float = 0.0
    """
    Execution time in seconds.

    Used for:
    - Performance monitoring
    - Timeout enforcement
    - Workflow optimization
    """

    impact: ActionImpact | None = None
    """
    What kind of changes this action made.

    Optional but recommended for constitutional governance.
    Helps the system understand the scope of changes.
    """

    logs: list[str] = field(default_factory=list)
    """
    Debug trace messages (internal use only, not shown to users).

    For troubleshooting and detailed audit trails.
    Logged at DEBUG level by default.
    """

    warnings: list[str] = field(default_factory=list)
    """
    Non-fatal issues encountered during execution.

    Action succeeded (ok=True) but these issues should be noted.
    Example: "Using fallback method due to missing dependency"
    """

    suggestions: list[str] = field(default_factory=list)
    """
    Recommended follow-up actions.

    Example: If a check finds violations, suggest the fix command.
    Enables autonomous agents to chain actions intelligently.
    """

    # Constitutional constant: Maximum allowed payload size (5MB)
    MAX_DATA_SIZE_BYTES = 5 * 1024 * 1024

    def __post_init__(self):
        """Validate ActionResult structure and size constraints."""
        if not isinstance(self.action_id, str) or not self.action_id:
            raise ValueError("action_id must be non-empty string")
        if not isinstance(self.data, dict):
            raise ValueError("data must be a dict")
        if not isinstance(self.ok, bool):
            raise ValueError("ok must be a boolean")

        # Enforce data size limit to prevent memory bloating in workflows
        try:
            # We use JSON serialization as a proxy for data size
            serialized = json.dumps(self.data, default=str)
            if len(serialized) > self.MAX_DATA_SIZE_BYTES:
                raise ValueError(
                    f"ActionResult.data exceeds size limit of {self.MAX_DATA_SIZE_BYTES} bytes "
                    f"(got {len(serialized)} bytes). Action: {self.action_id}"
                )
        except (TypeError, OverflowError):
            # If data isn't serializable, we warn but don't crash (logging handled by caller)
            pass

    # ------------------------------------------------------------------
    # Backwards compatibility for legacy CommandResult.name usage
    # ------------------------------------------------------------------
    @property
    # ID: c70bf747-67ee-4913-a8df-91e325b8021a
    def name(self) -> str:
        """
        Backwards-compatible alias for `action_id`.

        Older code (like CLI workflows and reporters) still expects
        `result.name`. New code should prefer `action_id`, but this
        keeps existing workflows running while we migrate.
        """
        return self.action_id


# Backward compatibility aliases (temporary - will be removed in future version)
CommandResult = ActionResult
"""
DEPRECATED: Use ActionResult instead.

This alias exists for backward compatibility during migration.
Will be removed once all commands are migrated to ActionResult.
"""
