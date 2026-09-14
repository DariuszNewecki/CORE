# src/shared/cli_types.py
"""
Constitutional CLI Framework - Shared types for CLI command contracts.

All core-admin commands should return CommandResult to enable:
1. Standardized orchestration (workflows can collect and report uniformly)
2. Machine-readable output (--format json support)
3. Constitutional governance (audit trails, policies)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ID: 433a8830-74fa-4337-8817-5e883d6424e6
class _WorkflowResultsMixin:
    """Shared computed properties for any workflow container that holds results.

    Eliminates AST duplication between WorkflowRun and DevSyncPhase.
    Both have a `results` field whose items expose `.ok` and `.duration_sec`.
    """

    results: list  # subclass dataclass field — accessed via self.results

    @property
    # ID: a8baadfa-8c65-4234-b300-30ce98704601
    def ok(self) -> bool:
        """Succeeds only if ALL results succeed."""
        return all(r.ok for r in self.results)

    @property
    # ID: 66e0b0f5-d47e-48cf-9bdc-2c8283b02d0d
    def total_duration(self) -> float:
        """Sum of all result durations."""
        return sum(r.duration_sec for r in self.results)


@dataclass
# ID: 27c34c59-3e89-475e-b014-d24668e4e67b
class CommandResult:
    """
    Standard result contract for all core-admin commands.

    Commands return data, not formatted output. Reporters handle presentation.
    This separation enables both human-friendly displays and machine parsing.
    """

    name: str
    """Command identifier (e.g., 'fix.ids', 'sync.knowledge')"""

    ok: bool
    """Binary success indicator. True = command achieved its goal."""

    data: dict[str, Any]
    """Domain-specific results. E.g., {'ids_fixed': 7, 'files_modified': 3}"""

    duration_sec: float = 0.0
    """Execution time in seconds"""

    logs: list[str] = field(default_factory=list)
    """Debug/trace messages (not shown to user by default)"""

    def __post_init__(self):
        """Validate the result structure."""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("CommandResult.name must be non-empty string")
        if not isinstance(self.data, dict):
            raise ValueError("CommandResult.data must be a dict")


@dataclass
# ID: f458eb09-9ed9-427e-af11-04e891474e14
class WorkflowRun(_WorkflowResultsMixin):
    """
    Collection of CommandResults representing a multi-step workflow.

    Used by orchestrators (dev.sync, check.audit) to group related operations.
    Inherits `ok` and `total_duration` from _WorkflowResultsMixin.
    """

    workflow_name: str
    """Workflow identifier (e.g., 'dev.sync', 'check.audit')"""

    results: list[CommandResult] = field(default_factory=list)
    """Individual command results in execution order"""

    # ID: fc0ea1d9-57f0-469f-b8b6-ed87cfbd7758
    def add(self, result: CommandResult) -> None:
        """Add a command result to this workflow."""
        self.results.append(result)
