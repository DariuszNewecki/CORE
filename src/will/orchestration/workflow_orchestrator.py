# src/will/orchestration/workflow_orchestrator.py

"""
Constitutional Workflow Orchestrator

Dynamically composes and executes phases based on workflow definitions
from the constitutional repository.

This replaces the hardcoded A3 loop with a constitutional, composable system.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from shared.path_resolver import PathResolver
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.phase_registry import PhaseRegistry


logger = getLogger(__name__)


@dataclass
# ID: 40124b3b-51eb-493c-bed4-e4a0b128443b
class WorkflowDefinition:
    """Parsed workflow definition from the constitutional repository."""

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


# ID: 8d6f2fb6-98b9-4ddc-9fd6-c161ccbac956
class WorkflowOrchestrator:
    """
    Constitutional workflow orchestrator.

    Reads workflow definitions from the constitutional repository
    and composes phases dynamically based on goal type.
    """

    def __init__(self, phase_registry: PhaseRegistry, path_resolver: PathResolver):
        self.phases = phase_registry
        self._paths = path_resolver
        self.tracer = DecisionTracer(self._paths)
        self._intent_repo = get_intent_repository()

    # ID: b86b70a4-9d28-4ec5-81cb-80bdc1578bc6
    def _load_workflow_definition(self, workflow_type: str) -> WorkflowDefinition:
        """Load workflow definition from the constitutional repository."""
        data = self._intent_repo.load_workflow(workflow_type)

        return WorkflowDefinition(
            workflow_type=data["workflow_type"],
            description=data["description"],
            phases=data["phases"],
            success_criteria=data["success_criteria"],
            write_required=data.get("write_required", True),
            dangerous=data.get("dangerous", False),
            timeout_minutes=data.get("timeout_minutes", 30),
        )

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
            workflow_type: Which workflow to use
            write: Whether to apply changes
        """
        workflow_start = time.time()

        logger.info("=" * 80)
        logger.info("CONSTITUTIONAL WORKFLOW EXECUTION")
        logger.info("Workflow: %s", workflow_type)
        logger.info("Goal: %s", goal)
        logger.info("Write Mode: %s", write)
        logger.info("=" * 80)

        workflow_def = self._load_workflow_definition(workflow_type)

        if workflow_def.write_required and not write:
            logger.info("Dry-run mode: No changes will be applied")

        context = WorkflowContext(goal=goal, workflow_type=workflow_type, write=write)

        phase_results = []
        for phase_name in workflow_def.phases:
            logger.info("")
            logger.info(" PHASE: %s", phase_name.upper())
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
                    context.results[phase_name] = result.data
                else:
                    logger.error("❌ Phase failed: %s", result.error)

                    phase_def = self._load_phase_definition(phase_name)
                    failure_mode = phase_def.get("failure_mode", "block")

                    if failure_mode == "block":
                        logger.error("⛔ Workflow blocked by phase failure")
                        break
                    if failure_mode == "warn":
                        logger.warning("⚠️  Phase failed but workflow continues")
                        continue

            except Exception as e:
                logger.error("💥 Phase crashed: %s", e, exc_info=True)
                phase_results.append(
                    PhaseResult(name=phase_name, ok=False, error=str(e))
                )
                break

        criteria_ok = self._evaluate_success_criteria(
            workflow_def.success_criteria, context
        )
        failed_phases = [p.name for p in phase_results if not p.ok]
        workflow_ok = criteria_ok and not failed_phases

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
        elif failed_phases:
            logger.warning(
                "⚠️  WORKFLOW COMPLETED IN DEGRADED MODE (failed phases: %s)",
                ", ".join(failed_phases),
            )
        else:
            logger.info("❌ WORKFLOW FAILED")
        logger.info("Total Duration: %.2fs", workflow_duration)
        logger.info("=" * 80)

        return result

    def _load_phase_definition(self, phase_name: str) -> dict[str, Any]:
        """Load phase definition from the constitutional repository."""
        return self._intent_repo.load_phase(phase_name)

    def _evaluate_success_criteria(
        self, criteria: dict[str, Any], context: WorkflowContext
    ) -> bool:
        """Evaluate workflow success criteria by searching through phase results."""
        flat_results: dict[str, Any] = {}
        for phase_data in context.results.values():
            if isinstance(phase_data, dict):
                flat_results.update(phase_data)

        for key, expected in criteria.items():
            actual = flat_results.get(key)

            if isinstance(expected, bool):
                if actual != expected:
                    if key == "canary_passes" and flat_results.get("skipped"):
                        continue
                    return False
            elif isinstance(expected, str) and expected.startswith(">"):
                try:
                    threshold = float(expected[1:].strip())
                    if actual is None or float(actual) <= threshold:
                        return False
                except (ValueError, TypeError):
                    return False

        return True
