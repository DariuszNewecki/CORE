# src/shared/models/workflow_models.py
# ID: shared.models.workflow

"""
Workflow orchestration data models.

Contains TWO workflow result types:
1. WorkflowResult - Legacy dev_sync result (uses WorkflowPhase with ActionResult list)
2. PhaseWorkflowResult - New constitutional workflow result (uses PhaseResult)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.action_types import ActionResult
from shared.models import ExecutionTask


# ============================================================================
# LEGACY WORKFLOW MODELS (for dev_sync_workflow)
# ============================================================================


@dataclass
# ID: 0352ca76-3ff1-4f84-971c-4572951b0b0c
class WorkflowPhase:
    """A logical phase in a workflow."""

    name: str
    actions: list[ActionResult] = field(default_factory=list)

    @property
    # ID: 39efa875-1c8f-47e0-90d2-33b94916de32
    def ok(self) -> bool:
        """Phase succeeds if all actions succeed."""
        return all(a.ok for a in self.actions)

    @property
    # ID: 45fd80e5-f4e7-49f6-a9a2-7dde8d57dd54
    def duration(self) -> float:
        """Total duration of all actions in this phase."""
        return sum(a.duration_sec for a in self.actions)


@dataclass
# ID: df39bc33-ee51-4bba-8bc8-f6bb0b368936
class WorkflowResult:
    """Result of a complete workflow execution (legacy dev_sync style)."""

    workflow_id: str
    phases: list[WorkflowPhase] = field(default_factory=list)

    @property
    # ID: 897f3983-2c7d-4b9c-9301-da47be7fc218
    def ok(self) -> bool:
        """Workflow succeeds if all phases succeed."""
        return all(p.ok for p in self.phases)

    @property
    # ID: 8c7c93d5-c288-4c76-a79e-83f1ca92c3b0
    def total_duration(self) -> float:
        """Total duration of entire workflow."""
        return sum(p.duration for p in self.phases)

    @property
    # ID: 2ac79685-321a-423b-989c-02d3201fb143
    def total_actions(self) -> int:
        """Total number of actions executed."""
        return sum(len(p.actions) for p in self.phases)

    @property
    # ID: a791f908-24e6-4774-8d94-cf9bbbbf1a8e
    def failed_actions(self) -> list[ActionResult]:
        """All failed actions across all phases."""
        failed = []
        for phase in self.phases:
            failed.extend([a for a in phase.actions if not a.ok])
        return failed


# ============================================================================
# CONSTITUTIONAL WORKFLOW MODELS (for new orchestrator)
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
