# src/agents/models.py
"""
Data models for the PlannerAgent and execution tasks.
Defines the structure of plans, tasks, and configurations.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class TaskStatus(Enum):
    """Enumeration of possible states for an ExecutionTask."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionProgress:
    """Represents the progress of a plan's execution."""

    total_tasks: int
    completed_tasks: int
    current_task: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING

    @property
    def completion_percentage(self) -> float:
        """
        Calculates the completion percentage of the plan as a float,
        returning 0 if there are no tasks.
        """
        return (
            (self.completed_tasks / self.total_tasks) * 100
            if self.total_tasks > 0
            else 0
        )


@dataclass
class PlannerConfig:
    """Configuration settings for the PlannerAgent's behavior."""

    max_retries: int = 3
    validation_enabled: bool = True
    auto_commit: bool = True
    rollback_on_failure: bool = True
    task_timeout: int = 300  # seconds


class TaskParams(BaseModel):
    """Data model for the parameters of a single task in an execution plan."""

    file_path: Optional[str] = None
    symbol_name: Optional[str] = None
    tag: Optional[str] = None
    code: Optional[str] = None
    justification: Optional[str] = None


class ExecutionTask(BaseModel):
    """Data model for a single, executable step in a plan."""

    step: str
    # --- THIS IS THE FIX ---
    action: Literal[
        "add_capability_tag", "create_file", "edit_function", "create_proposal"
    ]
    params: TaskParams
