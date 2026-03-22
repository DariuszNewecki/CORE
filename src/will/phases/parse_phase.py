# src/will/phases/parse_phase.py

"""
Parse Phase - Constitutional composite that drives PlannerAgent.

Converts interpreted intent (WorkflowContext.goal) into a structured
execution plan by invoking PlannerAgent directly.  Results are stored
under BOTH the canonical 'parse' key AND the legacy 'planning' key so
that CodeGenerationPhase (which reads 'planning') continues to work
without modification.

ARCHITECTURAL NOTE:
  PlanningPhase (src/will/phases/planning_phase.py) is a generic utility
  class with no constitutional-phase interface.  It has no execute() method
  and must NOT be used here.  The correct agent for constitutional planning
  is PlannerAgent (src/will/agents/planner_agent.py).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.agents.planner_agent import PlannerAgent


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: parse-phase-composite
# ID: 15c02b6a-ab2d-4026-ac2b-ab7a385f8c90
class ParsePhase:
    """
    Constitutional Parse phase.

    Converts interpreted intent into a structured operational plan by
    driving PlannerAgent.  Mirrors results under the legacy 'planning'
    key for backward compatibility with CodeGenerationPhase.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context

        # Resolve repo_path from git_service (always present after bootstrap).
        repo_path: Path = Path(core_context.git_service.repo_path)

        # Wire PlannerAgent from CoreContext services.
        # qdrant_service is optional — PlannerAgent degrades gracefully if absent.
        self._planner = PlannerAgent(
            cognitive_service=core_context.cognitive_service,
            repo_path=repo_path,
            qdrant_service=getattr(core_context, "qdrant_service", None),
        )

    # ID: 794bcd6c-de50-4ac2-868c-d6de52b277b9
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """
        Execute the parse phase: goal → execution plan via PlannerAgent.

        Stores the plan under both 'parse' and 'planning' in context.results
        so downstream phases that read either key continue to work.
        """
        start = time.time()

        goal: str = context.goal

        logger.info("🗂️  PARSE Phase: Planning goal: '%s'", goal)

        try:
            # PlannerAgent.create_execution_plan handles constitutional RAG,
            # action-registry introspection, and plan validation internally.
            plan = await self._planner.create_execution_plan(goal)
        except Exception as exc:
            logger.error("❌ PARSE: PlannerAgent failed: %s", exc, exc_info=True)
            return PhaseResult(
                name="parse",
                ok=False,
                error=f"Planning failed: {exc}",
                duration_sec=time.time() - start,
            )

        if not plan:
            logger.error("❌ PARSE: PlannerAgent returned an empty plan.")
            return PhaseResult(
                name="parse",
                ok=False,
                error="PlannerAgent produced no executable steps for this goal.",
                duration_sec=time.time() - start,
            )

        logger.info("✅ PARSE: Plan ready — %d steps", len(plan))
        for i, step in enumerate(plan, 1):
            logger.debug("   Step %d: [%s] %s", i, step.action, step.step)

        plan_data = {
            "execution_plan": plan,  # list[ExecutionTask] — consumed by CodeGenerationPhase
            "steps_count": len(plan),
            "goal": goal,
        }

        # Mirror under both keys.
        context.results["parse"] = plan_data
        context.results["planning"] = plan_data

        return PhaseResult(
            name="parse",
            ok=True,
            data=plan_data,
            duration_sec=time.time() - start,
        )
