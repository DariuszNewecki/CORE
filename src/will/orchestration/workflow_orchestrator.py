# src/will/orchestration/workflow_orchestrator.py
# ID: will.orchestration.workflow_orchestrator

"""
Constitutional Workflow Orchestrator

Dynamically composes and executes phases based on workflow definitions
from .intent/workflows/.

This replaces the hardcoded A3 loop with a constitutional, composable system.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import yaml

from shared.config import settings
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.phase_registry import PhaseRegistry


logger = getLogger(__name__)


@dataclass
# ID: 40124b3b-51eb-493c-bed4-e4a0b128443b
class WorkflowDefinition:
    """Parsed workflow definition from .intent/workflows/"""

    workflow_type: str
    description: str
    phases: list[str]
    success_criteria: dict[str, Any]
    write_required: bool = True
    dangerous: bool = False
    timeout_minutes: int = 30


@dataclass
# ID: 6554faa6-95b1-4695-a11a-6c1ee8b86d20
class WorkflowContext:
    """Shared context passed through all phases"""

    goal: str
    workflow_type: str
    write: bool
    results: dict[str, Any]  # Accumulates outputs from each phase

    def __init__(self, goal: str, workflow_type: str, write: bool):
        self.goal = goal
        self.workflow_type = workflow_type
        self.write = write
        self.results = {}


# ID: 8a7b6c5d-4e3f-2g1h-0i9j-8k7l6m5n4o3p
# ID: 8d6f2fb6-98b9-4ddc-9fd6-c161ccbac956
class WorkflowOrchestrator:
    """
    Constitutional workflow orchestrator.

    Reads workflow definitions from .intent/workflows/
    Composes phases dynamically based on goal type.
    """

    def __init__(self, phase_registry: PhaseRegistry):
        self.phases = phase_registry
        self.tracer = DecisionTracer()
        self.workflow_dir = settings.REPO_PATH / ".intent" / "workflows"

    # ID: 9b8c7d6e-5f4g-3h2i-1j0k-9l8m7n6o5p4q
    def _load_workflow_definition(self, workflow_type: str) -> WorkflowDefinition:
        """Load workflow definition from Constitution."""
        workflow_path = self.workflow_dir / f"{workflow_type}.yaml"

        if not workflow_path.exists():
            raise ValueError(
                f"Unknown workflow type: {workflow_type}. "
                f"Expected file: {workflow_path}"
            )

        with open(workflow_path) as f:
            data = yaml.safe_load(f)

        return WorkflowDefinition(
            workflow_type=data["workflow_type"],
            description=data["description"],
            phases=data["phases"],
            success_criteria=data["success_criteria"],
            write_required=data.get("write_required", True),
            dangerous=data.get("dangerous", False),
            timeout_minutes=data.get("timeout_minutes", 30),
        )

    # ID: 0c9d8e7f-6g5h-4i3j-2k1l-0m9n8o7p6q5r
    # ID: 754633b1-65fe-4cbb-b83b-c97a06cfac23
    async def execute_goal(
        self,
        goal: str,
        workflow_type: str,
        write: bool = False,
    ) -> PhaseWorkflowResult:
        """
        Execute a goal using the specified workflow pipeline.

        Args:
            goal: High-level objective
            workflow_type: Which workflow to use (from .intent/workflows/)
            write: Whether to apply changes
        """
        workflow_start = time.time()

        logger.info("=" * 80)
        logger.info("🎯 CONSTITUTIONAL WORKFLOW EXECUTION")
        logger.info("Workflow: %s", workflow_type)
        logger.info("Goal: %s", goal)
        logger.info("Write Mode: %s", write)
        logger.info("=" * 80)

        # Load workflow definition from Constitution
        workflow_def = self._load_workflow_definition(workflow_type)

        # Validate write mode if required
        if workflow_def.write_required and not write:
            logger.info("ℹ️  Dry-run mode: No changes will be applied")  # noqa: RUF001

        # Build execution context
        context = WorkflowContext(goal=goal, workflow_type=workflow_type, write=write)

        # Execute phase pipeline
        phase_results = []
        for phase_name in workflow_def.phases:
            logger.info("")
            logger.info("📍 PHASE: %s", phase_name.upper())
            logger.info("-" * 80)

            phase_start = time.time()

            try:
                phase = self.phases.get(phase_name)
                result = await phase.execute(context)

                phase_duration = time.time() - phase_start
                result.duration_sec = phase_duration

                phase_results.append(result)

                if result.ok:
                    logger.info("✅ Phase completed: %.2fs", phase_duration)
                    # Store phase outputs in context for next phase
                    context.results[phase_name] = result.data
                else:
                    logger.error("❌ Phase failed: %s", result.error)

                    # Check failure mode from phase definition
                    phase_def = self._load_phase_definition(phase_name)
                    failure_mode = phase_def.get("failure_mode", "block")

                    if failure_mode == "block":
                        logger.error("⛔ Workflow blocked by phase failure")
                        break
                    elif failure_mode == "warn":
                        logger.warning("⚠️  Phase failed but workflow continues")
                        continue

            except Exception as e:
                logger.error("💥 Phase crashed: %s", e, exc_info=True)
                phase_results.append(
                    PhaseResult(name=phase_name, ok=False, error=str(e))
                )
                break

        # Evaluate success criteria
        workflow_ok = self._evaluate_success_criteria(
            workflow_def.success_criteria, context
        )

        workflow_duration = time.time() - workflow_start

        result = PhaseWorkflowResult(
            ok=workflow_ok,
            workflow_type=workflow_type,
            phase_results=phase_results,
            total_duration=workflow_duration,
        )

        logger.info("=" * 80)
        if workflow_ok:
            logger.info("✅ WORKFLOW COMPLETED SUCCESSFULLY")
        else:
            logger.info("❌ WORKFLOW FAILED")
        logger.info("Total Duration: %.2fs", workflow_duration)
        logger.info("=" * 80)

        return result

    def _load_phase_definition(self, phase_name: str) -> dict:
        """Load phase definition from .intent/phases/"""
        phase_path = settings.REPO_PATH / ".intent" / "phases" / f"{phase_name}.yaml"
        with open(phase_path) as f:
            return yaml.safe_load(f)

    def _evaluate_success_criteria(
        self, criteria: dict[str, Any], context: WorkflowContext
    ) -> bool:
        """Evaluate workflow success criteria against results."""
        # Simple implementation - can be made more sophisticated
        for key, expected in criteria.items():
            actual = context.results.get(key)

            if isinstance(expected, bool):
                if actual != expected:
                    return False
            elif isinstance(expected, str) and expected.startswith(">"):
                threshold = float(expected[1:].strip())
                if actual is None or actual <= threshold:
                    return False

        return True
