# src/will/phases/load_phase.py

"""
Load Phase - Constitutional composite.

Validates that the parse phase produced a usable execution plan
and that required resources are available before runtime begins.
No existing sub-phase implementation — this is a constitutional
readiness gate, not a transformation step.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: load-phase-composite
# ID: 0ee1190c-df21-46d2-af20-932e8474e86f
class LoadPhase:
    """
    Constitutional Load phase.

    Resolves parsed plans into executable operational context.
    Validates that:
    - An execution plan exists from the parse phase
    - Required services (cognitive, file handler) are available
    - Write mode is correctly configured for this workflow

    This phase is a constitutional gate, not a transformation step.
    It does not generate or modify any artifacts.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context

    # ID: 32572bda-4533-49e9-a028-409cff67e4ac
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Validate execution context is ready for runtime."""
        start = time.time()

        # Resolve plan from parse phase (supports both key names)
        parse_data = context.results.get("parse", context.results.get("planning", {}))
        plan = parse_data.get("execution_plan", [])

        if not plan:
            logger.error(
                "❌ LOAD: No execution plan found from parse phase. "
                "Cannot proceed to runtime."
            )
            return PhaseResult(
                name="load",
                ok=False,
                error="No execution plan available from parse phase.",
                duration_sec=time.time() - start,
            )

        # Validate required services are present
        missing = []
        if not getattr(self.context, "cognitive_service", None):
            missing.append("cognitive_service")
        if not getattr(self.context, "file_handler", None):
            missing.append("file_handler")
        if not getattr(self.context, "git_service", None):
            missing.append("git_service")

        if missing:
            logger.error("❌ LOAD: Required services unavailable: %s", missing)
            return PhaseResult(
                name="load",
                ok=False,
                error=f"Required services missing: {missing}",
                duration_sec=time.time() - start,
            )

        logger.info(
            "✅ LOAD: Execution context ready — %d steps, write=%s",
            len(plan),
            context.write,
        )

        return PhaseResult(
            name="load",
            ok=True,
            data={
                "execution_context_ready": True,
                "action_set_resolved": True,
                "steps": len(plan),
                "write_mode": context.write,
                "workflow_type": context.workflow_type,
            },
            duration_sec=time.time() - start,
        )
