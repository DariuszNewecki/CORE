# src/shared/models/execution_models.py
"""
Defines the Pydantic models for representing autonomous execution plans and tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


# ID: 1a71c89f-73f0-436b-ad58-f24cfbdec162
class TaskParams(BaseModel):
    """Parameters for a single task in an execution plan."""

    # --- THIS IS THE FIX ---
    # The file_path is now optional to allow for tasks that don't operate on a single file.
    file_path: str | None = None
    # --- END OF FIX ---

    code: str | None = None
    symbol_name: str | None = None
    justification: str | None = None
    tag: str | None = None


# ID: e60af3be-15e5-4a35-a45a-8fc4eb6e5dbd
class ExecutionTask(BaseModel):
    """A single, validated step in an execution plan."""

    step: str
    action: str
    params: TaskParams


# ID: 73684d31-61e0-4f28-bb94-7134f296371b
class PlannerConfig(BaseModel):
    """Configuration for the Planner and Execution agents."""

    task_timeout: int = Field(default=300, description="Timeout for a single task.")
    rollback_on_failure: bool = Field(default=True, description="Rollback on failure.")
    auto_commit: bool = Field(default=True, description="Auto-commit changes.")


# ID: 1ccf34ef-9cea-4411-91b1-d93457a2b43a
class PlanExecutionError(Exception):
    """Custom exception for errors during plan execution."""

    def __init__(self, message: str, violations: list[dict] | None = None):
        super().__init__(message)
        self.violations = violations or []


# ============================================================================
# DETAILED PLAN MODELS (for SpecificationAgent output)
# ============================================================================


@dataclass
# ID: 1787d480-ac3f-4742-86d0-3fb773988f39
class DetailedPlanStep:
    """
    A plan step enriched with code specifications.
    This is the "Blueprint" for a single Atomic Action.
    """

    action: str
    """Atomic action ID (e.g., 'file.create', 'sync.db')"""

    description: str
    """Human-readable step description"""

    params: dict[str, Any]
    """Parameters for ActionExecutor"""

    is_critical: bool = True
    """If True, construction stops immediately if this step fails."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Traceability metadata (original task, pattern used, etc.)"""

    @classmethod
    # ID: fe4f9588-56c4-4e3e-976b-b51fbf7ed27f
    def from_execution_task(
        cls, task: ExecutionTask, code: str | None = None
    ) -> DetailedPlanStep:
        """
        Bridge: Converts a conceptual task from the Architect into a
        concrete blueprint for the Contractor.
        """
        # Convert Pydantic model to dict, removing None values
        params = task.params.model_dump(exclude_none=True)

        # Inject generated code if provided by the Engineer
        if code is not None:
            params["code"] = code

        return cls(
            action=task.action,
            description=task.step,
            params=params,
            is_critical=True,
            metadata={
                "original_task": task.step,
                "task_action": task.action,
            },
        )


@dataclass
# ID: 1bde9456-e31e-40a6-8474-5a07153f9d28
class DetailedPlan:
    """
    A full collection of blueprints (steps) for a goal.
    This is the core artifact of the Engineering phase.
    """

    goal: str
    """The high-level goal being achieved."""

    steps: list[DetailedPlanStep]
    """Sequence of executable blueprints."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Planning and retry metadata."""

    @property
    # ID: 3bd7567f-2ab4-48c0-97d7-7a6d9476b986
    def step_count(self) -> int:
        return len(self.steps)

    # ID: dbea8549-6bd6-489a-a527-2c472bf7abe7
    def get_steps_requiring_code(self) -> list[DetailedPlanStep]:
        """Filters for steps that involved code generation."""
        code_actions = {"file.create", "file.edit", "create_file", "edit_file"}
        return [s for s in self.steps if s.action in code_actions]
