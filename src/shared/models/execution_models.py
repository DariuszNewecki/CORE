# src/shared/models/execution_models.py
"""
Defines the Pydantic models for representing autonomous execution plans and tasks.

NOTE: DetailedPlan and DetailedPlanStep live in workflow_models.py (single source of truth).
They were previously duplicated here; removed to satisfy purity.no_ast_duplication.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from shared.infrastructure.intent.task_type_phases import allowed_task_types


# ADR-004: Vocabulary governed by .intent/enforcement/config/task_type_phases.yaml.
_ALLOWED_TASK_TYPES: frozenset[str] = allowed_task_types()


# ID: 1a71c89f-73f0-436b-ad58-f24cfbdec162
class TaskParams(BaseModel):
    """Parameters for a single task in an execution plan."""

    file_path: str | None = None
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
    task_type: str = "code_generation"

    @field_validator("task_type")
    @classmethod
    def _validate_task_type(cls, value: str) -> str:
        if value not in _ALLOWED_TASK_TYPES:
            raise ValueError(
                f"Invalid task_type {value!r}; allowed values are "
                f"{sorted(_ALLOWED_TASK_TYPES)}"
            )
        return value


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
