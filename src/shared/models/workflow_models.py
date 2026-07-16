# src/shared/models/workflow_models.py

"""
Workflow orchestration data models.

PhaseWorkflowResult is the constitutional workflow result type (PhaseResult
per phase). The legacy WorkflowResult/WorkflowPhase pair (ActionResult-list
style) was retired with dev_sync's migration (#805).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.models import ExecutionTask


# ============================================================================
# CONSTITUTIONAL WORKFLOW MODELS
# ============================================================================


@dataclass
# ID: 2a212a56-0e76-4c3a-8ba2-2b45f09a2a82
class PhaseResult:
    """Result from a single workflow phase execution."""

    name: str
    """Phase name (e.g., 'planning', 'code_generation')"""

    ok: bool
    """Whether the phase succeeded"""

    data: dict[str, Any] = field(default_factory=dict)
    """Phase outputs/artifacts"""

    error: str = ""
    """Error message if ok=False"""

    duration_sec: float = 0.0
    """Phase execution time in seconds"""


@dataclass
# ID: 223ab649-f786-41d4-aefc-a9b61a918757
class PhaseWorkflowResult:
    """Result of a complete constitutional workflow execution."""

    ok: bool
    """Overall workflow success"""

    workflow_type: str = ""
    """Type of workflow executed (e.g., 'refactor_modularity')"""

    phase_results: list[PhaseResult] = field(default_factory=list)
    """Results from each phase"""

    total_duration: float = 0.0
    """Total workflow time in seconds"""

    @property
    # ID: 3cf75721-9497-409a-941c-3ba098d6ab68
    def total_actions(self) -> int:
        """Count of all phase executions"""
        return len(self.phase_results)

    @property
    # ID: fc7fe700-9e47-4e72-937e-23b21176831f
    def failed_actions(self) -> list[PhaseResult]:
        """All failed phases"""
        return [p for p in self.phase_results if not p.ok]


# ============================================================================
# A3 MODELS (for SpecificationAgent output)
# ============================================================================


@dataclass
# ID: 333b383a-fcfd-448a-9868-302fabf1f747
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
    # ID: 95466de7-d697-47c5-ad53-fd73741734f3
    def from_execution_task(
        cls, task: ExecutionTask, code: str | None = None
    ) -> DetailedPlanStep:
        """
        Bridge: Converts a conceptual task from the Architect into a
        concrete blueprint for the Contractor.

        ROBUSTNESS FIX: Some LLMs (like DeepSeek) incorrectly put the file_path
        value into the code field. We detect and fix this here.
        """
        # Convert Pydantic model to dict, removing None values
        params = task.params.model_dump(exclude_none=True)

        # ROBUSTNESS FIX: If params["code"] looks like a file path (not actual code),
        # remove it so the generated code can replace it properly
        if "code" in params and "file_path" in params:
            # If code field contains the file_path value, it's an LLM error
            if params["code"] == params["file_path"]:
                # Remove the incorrect code value
                del params["code"]

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
# ID: e19bec73-be0f-4e9b-9bf6-8a9472a70344
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
    # ID: 5f6a0c6b-8079-4da4-a5f0-18ff886df8a6
    def step_count(self) -> int:
        return len(self.steps)

    # ID: 085444e1-3e1d-4287-aadb-9faceb938311
    def get_steps_requiring_code(self) -> list[DetailedPlanStep]:
        """Filters for steps that involved code generation."""
        code_actions = {"file.create", "file.edit", "create_file", "edit_file"}
        return [s for s in self.steps if s.action in code_actions]


@dataclass
# ID: 3d561dda-83aa-4108-898a-6df738e0d9ab
class ExecutionResults:
    """Results from code execution/application."""

    success: bool
    files_written: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
