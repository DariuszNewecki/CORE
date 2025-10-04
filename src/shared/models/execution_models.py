# src/shared/models/execution_models.py
"""
Defines the Pydantic models for representing autonomous execution plans and tasks.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ID: 1a71c89f-73f0-436b-ad58-f24cfbdec162
class TaskParams(BaseModel):
    """Parameters for a single task in an execution plan."""

    file_path: str
    code: Optional[str] = None
    symbol_name: Optional[str] = None
    justification: Optional[str] = None
    tag: Optional[str] = None


# ID: 3173b37e-a64f-4227-92c5-84e444b68dc1
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

    def __init__(self, message: str, violations: List[dict] | None = None):
        super().__init__(message)
        self.violations = violations or []
