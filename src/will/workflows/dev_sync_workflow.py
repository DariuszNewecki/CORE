# src/will/workflows/dev_sync_workflow.py

"""
Dev Sync Workflow - Constitutional Orchestration

Composes atomic actions into a governed workflow:
1. Fix Phase: Make code constitutional
2. Sync Phase: Propagate clean state to DB and vectors

Returns PhaseWorkflowResult (the constitutional workflow result type).
Consumers (CLI dev sync, DbSyncWorker, sync_runner) rely only on `.ok`;
per-action outcomes are carried in each PhaseResult's `data["actions"]`.

DRY-RUN FIX (VITAL):
- Do NOT hardcode write=True.
- Propagate the workflow write flag to every atomic action.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult


if TYPE_CHECKING:
    from shared.action_types import ActionResult
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e
class DevSyncWorkflow:
    """
    Constitutional orchestration of the dev-sync workflow.
    """

    def __init__(self, context: CoreContext):
        self.context = context
        # The ActionExecutor is the central gateway for all changes
        self.executor = ActionExecutor(context)

    # ID: c2d3e4f5-6a7b-8c9d-0e1f-2a3b4c5d6e7f
    async def run(self, *, write: bool = False) -> PhaseWorkflowResult:
        """Execute the complete dev-sync workflow."""
        mode = "WRITE" if write else "DRY-RUN"
        logger.info("🚀 Starting dev-sync workflow (%s)...", mode)

        phases: list[PhaseResult] = []

        # Phase 1: Fix (Clean the Body)
        fix_phase = await self._run_fix_phase(write=write)
        phases.append(fix_phase)

        if not fix_phase.ok:
            logger.warning("❌ Fix phase failed, skipping sync phase")
            return self._build_result(phases)

        # Phase 2: Sync (Update the Mind/Memory)
        sync_phase = await self._run_sync_phase(write=write)
        phases.append(sync_phase)

        result = self._build_result(phases)
        if result.ok:
            logger.info("✅ Dev-sync workflow completed successfully (%s)", mode)
        else:
            logger.warning("⚠️  Dev-sync workflow completed with failures (%s)", mode)

        return result

    # ID: 37d0c9f7-7402-49e5-98ff-0fe95b2ade37
    async def _run_fix_phase(self, *, write: bool) -> PhaseResult:
        """Phase 1: Make code constitutional."""
        logger.info("📝 Phase 1: Fix (Code Compliance) [write=%s]", write)
        actions: list[ActionResult] = []

        # Action: Fix file headers (must run before IDs to avoid prepend conflicts)
        actions.append(
            await self.executor.execute(action_id="fix.headers", write=write)
        )

        # Action: Fix IDs
        actions.append(await self.executor.execute(action_id="fix.ids", write=write))

        # TEMPORARILY DISABLED: Run fix.docstrings separately (bulk initial pass)
        # actions.append(
        #     await self.executor.execute(action_id="fix.docstrings", write=write)
        # )

        # Action: Format code (always last — cleans up after all other fixers)
        actions.append(await self.executor.execute(action_id="fix.format", write=write))

        return self._build_phase("fix", actions)

    # ID: 4cb4b930-eddf-4bd4-872b-f049ede7792a
    async def _run_sync_phase(self, *, write: bool) -> PhaseResult:
        """Phase 2: Propagate state to DB and Vectors."""
        logger.info("🔄 Phase 2: Sync (State & Memory) [write=%s]", write)
        actions: list[ActionResult] = []

        # In DRY-RUN, do NOT write to DB/Vectors.
        # We still execute actions with write=False so they can perform
        # read-only checks / compute deltas if implemented that way.
        db_sync_res = await self.executor.execute(action_id="sync.db", write=write)
        actions.append(db_sync_res)

        if not db_sync_res.ok:
            logger.error("❌ sync.db failed, skipping vectorization")
            return self._build_phase("sync", actions)

        actions.append(
            await self.executor.execute(action_id="sync.vectors_code", write=write)
        )

        return self._build_phase("sync", actions)

    @staticmethod
    def _build_phase(name: str, actions: list[ActionResult]) -> PhaseResult:
        """Fold executed ActionResults into one PhaseResult."""
        failed = [a for a in actions if not a.ok]
        return PhaseResult(
            name=name,
            ok=not failed,
            data={
                "actions": {
                    a.action_id: {"ok": a.ok, "duration_sec": a.duration_sec}
                    for a in actions
                }
            },
            error="; ".join(
                f"{a.action_id}: {a.data.get('error', 'failed')}" for a in failed
            ),
            duration_sec=sum(a.duration_sec for a in actions),
        )

    @staticmethod
    def _build_result(phases: list[PhaseResult]) -> PhaseWorkflowResult:
        """Fold phase results into the constitutional workflow result."""
        return PhaseWorkflowResult(
            ok=all(p.ok for p in phases),
            workflow_type="dev_sync",
            phase_results=list(phases),
            total_duration=sum(p.duration_sec for p in phases),
        )
