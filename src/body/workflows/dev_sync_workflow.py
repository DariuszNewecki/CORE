# src/body/workflows/dev_sync_workflow.py
# ID: ef65dfd2-cd77-48d0-beeb-332246e27eb4

"""
Dev Sync Workflow - Constitutional Orchestration

Composes atomic actions into a governed workflow:
1. Fix Phase: Make code constitutional
2. Sync Phase: Propagate clean state to DB and vectors

CONSTITUTIONAL FIX:
- Aligned action names with the Atomic Registry (fix.ids, sync.db, etc).
- Corrected method calls from 'execute_action' to 'execute' to match ActionExecutor.

DRY-RUN FIX (VITAL):
- Do NOT hardcode write=True.
- Propagate the workflow write flag to every atomic action.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger
from shared.models.workflow_models import WorkflowPhase, WorkflowResult


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 834371ad-d69b-4c29-9f4d-7694a4a05179
# ID: b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e
class DevSyncWorkflow:
    """
    Constitutional orchestration of the dev-sync workflow.
    """

    def __init__(self, context: CoreContext):
        self.context = context
        # The ActionExecutor is the central gateway for all changes
        self.executor = ActionExecutor(context)

    # ID: 4a082bd8-28f6-4821-a3a5-365e243c1df2
    # ID: c2d3e4f5-6a7b-8c9d-0e1f-2a3b4c5d6e7f
    async def run(self, *, write: bool = False) -> WorkflowResult:
        """Execute the complete dev-sync workflow."""
        mode = "WRITE" if write else "DRY-RUN"
        logger.info("🚀 Starting dev-sync workflow (%s)...", mode)

        result = WorkflowResult(workflow_id="dev_sync")

        # Phase 1: Fix (Clean the Body)
        fix_phase = await self._run_fix_phase(write=write)
        result.phases.append(fix_phase)

        if not fix_phase.ok:
            logger.warning("❌ Fix phase failed, skipping sync phase")
            return result

        # Phase 2: Sync (Update the Mind/Memory)
        sync_phase = await self._run_sync_phase(write=write)
        result.phases.append(sync_phase)

        if result.ok:
            logger.info("✅ Dev-sync workflow completed successfully (%s)", mode)
        else:
            logger.warning("⚠️  Dev-sync workflow completed with failures (%s)", mode)

        return result

    # ID: 37d0c9f7-7402-49e5-98ff-0fe95b2ade37
    async def _run_fix_phase(self, *, write: bool) -> WorkflowPhase:
        """Phase 1: Make code constitutional."""
        phase = WorkflowPhase(name="fix")
        logger.info("📝 Phase 1: Fix (Code Compliance) [write=%s]", write)

        # Action: Fix IDs (ID: fix.ids)
        res = await self.executor.execute(action_id="fix.ids", write=write)
        phase.actions.append(res)

        # Action: Add docstrings (ID: fix.docstrings)
        res = await self.executor.execute(action_id="fix.docstrings", write=write)
        phase.actions.append(res)

        # Action: Format code (ID: fix.format)
        res = await self.executor.execute(action_id="fix.format", write=write)
        phase.actions.append(res)

        return phase

    # ID: 4cb4b930-eddf-4bd4-872b-f049ede7792a
    async def _run_sync_phase(self, *, write: bool) -> WorkflowPhase:
        """Phase 2: Propagate state to DB and Vectors."""
        phase = WorkflowPhase(name="sync")
        logger.info("🔄 Phase 2: Sync (State & Memory) [write=%s]", write)

        # In DRY-RUN, do NOT write to DB/Vectors.
        # We still execute actions with write=False so they can perform
        # read-only checks / compute deltas if implemented that way.
        db_sync_res = await self.executor.execute(action_id="sync.db", write=write)
        phase.actions.append(db_sync_res)

        if not db_sync_res.ok:
            logger.error("❌ sync.db failed, skipping vectorization")
            return phase

        vectorize_res = await self.executor.execute(
            action_id="sync.vectors.code", write=write
        )
        phase.actions.append(vectorize_res)

        return phase
