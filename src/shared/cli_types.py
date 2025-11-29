# src/shared/cli_types.py

"""
Shared types for CLI command contracts.

All core-admin commands should return CommandResult to enable:
1. Standardized orchestration (workflows can collect and report uniformly)
2. Machine-readable output (--format json support)
3. Constitutional governance (audit trails, policies)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
        """Validate the result structure"""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("CommandResult.name must be non-empty string")
        if not isinstance(self.data, dict):
            raise ValueError("CommandResult.data must be a dict")


@dataclass
# ID: f458eb09-9ed9-427e-af11-04e891474e14
class WorkflowRun:
    """
    Collection of CommandResults representing a multi-step workflow.

    Used by orchestrators (dev.sync, check.audit) to group related operations.
    """

    workflow_name: str
    """Workflow identifier (e.g., 'dev.sync', 'check.audit')"""

    results: list[CommandResult] = field(default_factory=list)
    """Individual command results in execution order"""

    @property
    # ID: f94b2822-4fda-4a3c-b528-ef9d33606c35
    def ok(self) -> bool:
        """Workflow succeeds only if ALL commands succeed"""
        return all(r.ok for r in self.results)

    @property
    # ID: cecc4af0-5c6f-4daf-a819-8f83478d8dfd
    def total_duration(self) -> float:
        """Sum of all command durations"""
        return sum(r.duration_sec for r in self.results)

    # ID: fc0ea1d9-57f0-469f-b8b6-ed87cfbd7758
    def add(self, result: CommandResult):
        """Add a command result to this workflow"""
        self.results.append(result)
