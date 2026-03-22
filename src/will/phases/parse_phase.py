# src/will/phases/parse_phase.py

"""
Parse Phase - Constitutional composite wrapping PlanningPhase.

Maps the constitutional 'parse' phase to the existing PlanningPhase
implementation. Also mirrors results under the legacy 'planning' key
so downstream phases (CodeGenerationPhase) can find them without change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.phases.planning_phase import PlanningPhase


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: parse-phase-composite
# ID: 15c02b6a-ab2d-4026-ac2b-ab7a385f8c90
class ParsePhase:
    """
    Constitutional Parse phase.

    Converts interpreted intent into a structured operational plan.
    Delegates to PlanningPhase and mirrors results under the legacy
    'planning' key for backward compatibility with CodeGenerationPhase.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self._planning = PlanningPhase(core_context)

    # ID: 794bcd6c-de50-4ac2-868c-d6de52b277b9
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute parse phase via PlanningPhase."""
        result = await self._planning.execute(context)

        if result.ok:
            # Mirror under legacy key so CodeGenerationPhase can find it
            context.results["planning"] = result.data
            logger.debug(
                "✅ PARSE: plan ready (%d steps)",
                result.data.get("steps_count", 0),
            )

        return PhaseResult(
            name="parse",
            ok=result.ok,
            data=result.data,
            error=result.error,
            duration_sec=result.duration_sec,
        )
