# src/body/workflows/dev_sync_workflow.py
# ID: workflows.dev_sync
"""
Dev Sync Workflow - Constitutional Orchestration

Composes atomic actions into a governed workflow:
1. Fix Phase: Make code constitutional
2. Sync Phase: Propagate clean state to DB and vectors

This orchestrator now routes all actions through the ActionExecutor gateway
to ensure consistent governance, auditing, and automatic dependency injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.action_types import ActionResult
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@dataclass
# ID: a1b2c3d4-5e6f-7890-abcd-ef1234567890
class WorkflowPhase:
    """A logical phase in a workflow."""

    name: str
    """Human-readable phase name"""

    actions: list[ActionResult] = field(default_factory=list)
    """Results from actions executed in this phase"""

    @property
    # ID: b2c3d4e5-6f78-90ab-cdef-1234567890ab
    def ok(self) -> bool:
        """Phase succeeds if all actions succeed."""
        return all(a.ok for a in self.actions)

    @property
    # ID: c3d4e5f6-7890-abcd-ef12-34567890abcd
    def duration(self) -> float:
        """Total duration of all actions in this phase."""
        return sum(a.duration_sec for a in self.actions)


@dataclass
# ID: d4e5f678-90ab-cdef-1234-567890abcdef
class WorkflowResult:
    """Result of a complete workflow execution."""

    workflow_id: str
    """Workflow identifier (e.g., 'dev.sync')"""

    phases: list[WorkflowPhase] = field(default_factory=list)
    """All phases executed"""

    @property
    # ID: e5f67890-abcd-ef12-3456-7890abcdef12
    def ok(self) -> bool:
        """Workflow succeeds if all phases succeed."""
        return all(p.ok for p in self.phases)

    @property
    # ID: f6789012-3456-789a-bcde-f0123456789a
    def total_duration(self) -> float:
        """Total duration of entire workflow."""
        return sum(p.duration for p in self.phases)

    @property
    # ID: 01234567-89ab-cdef-0123-456789abcdef
    def total_actions(self) -> int:
        """Total number of actions executed."""
        return sum(len(p.actions) for p in self.phases)

    @property
    # ID: 12345678-9abc-def0-1234-56789abcdef0
    def failed_actions(self) -> list[ActionResult]:
        """All failed actions across all phases."""
        failed = []
        for phase in self.phases:
            failed.extend([a for a in phase.actions if not a.ok])
        return failed


# ID: 23456789-abcd-ef01-2345-6789abcdef01
class DevSyncWorkflow:
    """
    Dev Sync Workflow Orchestrator.

    Composes atomic actions into a governed workflow that:
    1. Fixes code to be constitutional
    2. Syncs clean code to DB and vectors
    """

    def __init__(self, core_context: CoreContext, write: bool = False):
        self.core_context = core_context
        self.write = write
        self.result = WorkflowResult(workflow_id="dev.sync")

        # We now use the ActionExecutor Gateway for all execution
        self.gateway = ActionExecutor(core_context)

    # ID: 34567890-abcd-ef01-2345-6789abcdef01
    async def execute(self) -> WorkflowResult:
        """
        Execute the complete dev sync workflow.
        """
        logger.info("Starting dev.sync workflow (write=%s)", self.write)

        # Phase 1: Fix code
        await self._execute_fix_phase()

        # Phase 2: Sync state
        # Only sync if fix phase succeeded
        if self.result.phases[0].ok:
            await self._execute_sync_phase()
        else:
            logger.warning("Skipping sync phase due to fix phase failures")

        logger.info(
            "Dev sync workflow complete: %s actions in %.2fs",
            self.result.total_actions,
            self.result.total_duration,
        )

        return self.result

    # ID: 45678901-2345-6789-abcd-ef0123456789
    async def _execute_fix_phase(self) -> None:
        """Execute all fix actions via the Gateway."""
        phase = WorkflowPhase(name="Fix Code")
        logger.info("Starting Fix Phase")

        # By using self.gateway.execute(), the Gateway automatically
        # injects core_context where needed and checks the IntentGuard.

        # 1. Format
        phase.actions.append(await self.gateway.execute("fix.format", write=self.write))

        # 2. Assign IDs
        phase.actions.append(await self.gateway.execute("fix.ids", write=self.write))

        # 3. Fix headers
        phase.actions.append(
            await self.gateway.execute("fix.headers", write=self.write)
        )

        # 4. Fix docstrings
        phase.actions.append(
            await self.gateway.execute("fix.docstrings", write=self.write)
        )

        # 5. Fix logging
        phase.actions.append(
            await self.gateway.execute("fix.logging", write=self.write)
        )

        self.result.phases.append(phase)
        logger.info(
            "Fix Phase complete: %d/%d actions succeeded",
            sum(1 for a in phase.actions if a.ok),
            len(phase.actions),
        )

    # ID: 56789012-3456-789a-bcde-f0123456789a
    async def _execute_sync_phase(self) -> None:
        """Execute all sync actions via the Gateway."""
        phase = WorkflowPhase(name="Sync State")
        logger.info("Starting Sync Phase")

        # 1. Sync to database
        sync_db_result = await self.gateway.execute("sync.db", write=self.write)
        phase.actions.append(sync_db_result)

        # 2. Vectorize code (only if DB sync succeeded)
        if sync_db_result.ok:
            phase.actions.append(
                await self.gateway.execute(
                    "sync.vectors.code", write=self.write, force=False
                )
            )
        else:
            logger.warning("Skipping code vectorization due to DB sync failure")

        # 3. Vectorize constitution (optional)
        if self.write:
            # We wrap this in a try-except to handle cases where embeddings aren't configured
            try:
                result = await self.gateway.execute(
                    "sync.vectors.constitution", write=self.write
                )
                phase.actions.append(result)
            except Exception as e:
                logger.info(
                    "Skipping constitutional vectorization (non-critical): %s", e
                )

        self.result.phases.append(phase)
        logger.info(
            "Sync Phase complete: %d/%d actions succeeded",
            sum(1 for a in phase.actions if a.ok),
            len(phase.actions),
        )
