# src/will/phases/runtime_phase.py

"""
Runtime Phase - Constitutional composite.

Routes to the correct runtime sub-implementation based on workflow_type.
Enforces the constitutional boundary: runtime generates and transforms
candidate artifacts but does not evaluate rules or commit changes.

Routing:
  refactor_modularity      → CodeGenerationPhase
  coverage_remediation     → CodeGenerationPhase (TestGenerationPhase is
                             a stub; actual remediation uses batch service)
  full_feature_development → CodeGenerationPhase + TestGenerationPhase
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.phases.code_generation_phase import CodeGenerationPhase
from will.phases.test_generation_phase import TestGenerationPhase


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)

_WORKFLOW_ROUTING: dict[str, list[str]] = {
    "refactor_modularity": ["code_generation"],
    "coverage_remediation": ["code_generation"],
    "full_feature_development": ["code_generation", "test_generation"],
}


# ID: runtime-phase-composite
# ID: 69556bba-c5d1-48a1-91eb-5fc9f1bb8543
class RuntimePhase:
    """
    Constitutional Runtime phase.

    Selects and executes the appropriate sub-phases for the active
    workflow type. All sub-phases operate on candidate artifacts only —
    no rule evaluation, no commits.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self._code_gen = CodeGenerationPhase(core_context)
        self._test_gen = TestGenerationPhase(core_context)

    # ID: 8a11bc67-8e95-4594-9631-fc77299a9d9e
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute runtime sub-phases for the active workflow."""
        start = time.time()

        workflow_type = context.workflow_type
        sub_phases = _WORKFLOW_ROUTING.get(workflow_type, ["code_generation"])

        logger.info(
            "🔧 RUNTIME: workflow=%s, sub-phases=%s",
            workflow_type,
            sub_phases,
        )

        aggregated_data: dict = {}
        last_error = ""

        for sub_phase_name in sub_phases:
            if sub_phase_name == "code_generation":
                result = await self._code_gen.execute(context)
            elif sub_phase_name == "test_generation":
                result = await self._test_gen.execute(context)
            else:
                logger.warning(
                    "Unknown runtime sub-phase: %s — skipping", sub_phase_name
                )
                continue

            # Surface sub-phase results into context so audit phases can find them
            context.results[sub_phase_name] = result.data
            aggregated_data[sub_phase_name] = result.data

            if not result.ok:
                logger.error(
                    "❌ RUNTIME: sub-phase '%s' failed: %s",
                    sub_phase_name,
                    result.error,
                )
                return PhaseResult(
                    name="runtime",
                    ok=False,
                    error=f"{sub_phase_name} failed: {result.error}",
                    data=aggregated_data,
                    duration_sec=time.time() - start,
                )

            logger.info("✅ RUNTIME: sub-phase '%s' complete", sub_phase_name)

        return PhaseResult(
            name="runtime",
            ok=True,
            data={
                "candidate_outputs_produced": True,
                **aggregated_data,
            },
            duration_sec=time.time() - start,
        )
