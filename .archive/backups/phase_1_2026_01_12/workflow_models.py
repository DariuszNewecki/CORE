# src/shared/models/workflow_models.py
# ID: shared.models.workflow

"""
Workflow orchestration data models for A3 autonomous operations.

These models define the "Universal Language" spoken between:
1. Architecture (PlannerAgent)
2. Engineering (SpecificationAgent)
3. Packaging (Crate Action)
4. Construction (ExecutionAgent)

Constitutional Alignment:
- Traceability: All models are serializable for the Action Log (SSOT).
- Safety: Validates plan structure before execution.
- UNIX-Compliant: Strictly separates "What to do" from "How to do it".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.action_types import ActionResult
from shared.models import ExecutionTask


@dataclass
# ID: 80630918-27a0-4d3e-b299-340cb5fba007
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
    """
    Parameters for ActionExecutor.
    Can be empty for actions that target the whole system (e.g., fix.logging).
    """

    is_critical: bool = True
    """If True, construction stops immediately if this step fails."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Traceability metadata (original task, pattern used, etc.)"""

    @classmethod
    # ID: fd983f1b-73b6-4ec2-978f-5f106c789d79
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
# ID: 7e142acb-9a49-4717-8cfe-2fe65a2e2f21
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

    def __post_init__(self):
        """Constitutional Contract Validation."""
        if not self.goal:
            raise ValueError("DetailedPlan.goal cannot be empty")

        # A3 LOOP FIX: Allow empty steps only if the plan explicitly represents a failure.
        # This matches the Orchestrator's _create_failed_workflow_result() logic.
        is_failure = self.metadata.get("failed_at") is not None

        if not self.steps and not is_failure:
            raise ValueError("DetailedPlan.steps cannot be empty")

        # Validate each step's structure
        for i, step in enumerate(self.steps, 1):
            if not step.action:
                raise ValueError(f"Step {i} is missing an action ID.")

            # FIXED: We allow empty dicts {} but reject None or invalid types.
            # This allows actions like fix.logging to pass validation.
            if not isinstance(step.params, dict):
                raise ValueError(f"Step {i} (action={step.action}) has invalid params.")

    @property
    # ID: 9db20756-d02f-468b-bc8b-c63835bbd49d
    def step_count(self) -> int:
        return len(self.steps)

    # ID: 011b289a-495d-407c-b4b3-5fd1037e3ef8
    def get_steps_requiring_code(self) -> list[DetailedPlanStep]:
        """Filters for steps that involved code generation."""
        code_actions = {"file.create", "file.edit", "create_file", "edit_file"}
        return [s for s in self.steps if s.action in code_actions]


@dataclass
# ID: 42f0d991-9936-426d-85b7-4541a3ec8eed
class ExecutionResults:
    """
    The outcome of the Construction phase.
    Produced by the ExecutionAgent.
    """

    steps: list[ActionResult]
    """The resulting ActionResult for every blueprint executed."""

    success_count: int
    failure_count: int
    total_duration_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)

    # ID: cb531304-3ade-4275-8d00-d582360db4a0
    def all_succeeded(self) -> bool:
        return self.failure_count == 0

    @property
    # ID: 5d75ef43-3d0f-4b09-bfbf-856e293be19a
    def success_rate(self) -> float:
        total = len(self.steps)
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100.0

    # ID: 36165ef6-a47f-4a51-b7d4-7353f64d9a5f
    def get_first_failure(self) -> tuple[int, ActionResult] | None:
        for i, res in enumerate(self.steps, 1):
            if not res.ok:
                return (i, res)
        return None


@dataclass
# ID: eafd25aa-b788-47ca-946c-0eafc00d6191
class WorkflowResult:
    """
    The final 'Evidence Package' returned by the Orchestrator.
    Summarizes the entire A3 loop from Goal to final Construction.
    """

    goal: str
    detailed_plan: DetailedPlan
    execution_results: ExecutionResults
    success: bool
    total_duration_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)

    # ID: 9f4df1a0-1222-4925-87d0-5641cc40b7dc
    def summary(self) -> str:
        """User-facing summary of the autonomous cycle."""
        lines = [
            f"Goal: {self.goal}",
            f"Result: {'✅ SUCCESS' if self.success else '❌ FAILED'}",
            f"Duration: {self.total_duration_sec:.2f}s",
            f"Steps Executed: {self.detailed_plan.step_count}",
            f"Success Rate: {self.execution_results.success_rate:.1f}%",
        ]

        if not self.success:
            fail_point = self.execution_results.get_first_failure()
            if fail_point:
                step_idx, result = fail_point
                error = result.data.get("error", "Unspecified execution error")
                lines.append(f"Failure Point: Step {step_idx} ({result.action_id})")
                lines.append(f"Error Detail: {error}")

        return "\n".join(lines)
