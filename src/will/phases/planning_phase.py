# src/will/phases/planning_phase.py
# ID: 82e82bda-a9f2-40db-8e0c-83b0d2fa3339

"""
Planning Phase Implementation

Analyzes goal and creates execution strategy.
This is the "Architect" phase - no code generation.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.agents.planner_agent import PlannerAgent
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 99d77f4e-6924-49aa-8d14-23c026346ce1
# ID: 84eac1a4-e2c5-4861-a76f-8950fefab23a
class PlanningPhase:
    """
    Strategic planning phase.

    Produces:
    - Execution plan (conceptual steps)
    - Affected files
    - Risk assessment
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self.tracer = DecisionTracer()

    # ID: 4566200d-0e73-416e-ae02-c1341d0a6797
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute planning phase"""
        start = time.time()

        try:
            # Initialize planner agent (only takes cognitive_service)
            planner = PlannerAgent(
                cognitive_service=self.context.cognitive_service,
            )

            # Create execution plan
            logger.info("🧠 Analyzing goal and creating strategy...")
            plan = await planner.create_execution_plan(
                goal=context.goal,
                reconnaissance_report="",  # Could load from context
            )

            # Trace decision
            self.tracer.record(
                agent="PlanningPhase",
                decision_type="plan_created",
                rationale=f"Created plan with {len(plan)} steps",
                chosen_action=f"Generated {len(plan)}-step execution plan",
                context={"steps": len(plan), "goal": context.goal},
            )

            duration = time.time() - start

            return PhaseResult(
                name="planning",
                ok=True,
                data={
                    "execution_plan": plan,
                    "steps_count": len(plan),
                },
                duration_sec=duration,
            )

        except Exception as e:
            logger.error("Planning failed: %s", e, exc_info=True)
            duration = time.time() - start

            return PhaseResult(
                name="planning",
                ok=False,
                error=str(e),
                duration_sec=duration,
            )
