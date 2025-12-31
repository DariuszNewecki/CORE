# src/body/workflows/dev_sync_workflow.py
# ID: workflows.dev_sync
"""
Dev Sync Workflow - Constitutional Orchestration

Composes atomic actions into a governed workflow:
1. Fix Phase: Make code constitutional
2. Sync Phase: Propagate clean state to DB and vectors

Follows workflow_rules.json policy:
- Each action is independent
- Each action returns ActionResult
- Phases organize related actions
- Full governance and audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Import from body.atomic package (which has the aliases)
from body.atomic import (
    action_fix_docstrings,
    action_fix_format,  # This is the alias for action_format_code
    action_fix_headers,
    action_fix_ids,
    action_fix_logging,
    action_sync_code_vectors,
    action_sync_constitutional_vectors,
    action_sync_database,
)
from shared.action_types import ActionResult
from shared.context import CoreContext
from shared.logger import getLogger


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

    Constitutional guarantees:
    - Every action is independent
    - Every action is auditable
    - Failures are traceable
    - Results are composable
    """

    def __init__(self, core_context: CoreContext, write: bool = False):
        self.core_context = core_context
        self.write = write
        self.result = WorkflowResult(workflow_id="dev.sync")

    # ID: 34567890-abcd-ef01-2345-6789abcdef01
    async def execute(self) -> WorkflowResult:
        """
        Execute the complete dev sync workflow.

        Returns:
            WorkflowResult with all phases and actions
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
        """Execute all fix actions."""
        phase = WorkflowPhase(name="Fix Code")
        logger.info("Starting Fix Phase")

        # Action 1: Format code (Black + Ruff)
        result = await action_fix_format(write=self.write)
        phase.actions.append(result)
        logger.info("fix.format: %s", "OK" if result.ok else f"FAILED - {result.data}")

        # Action 2: Assign IDs
        result = await action_fix_ids(write=self.write)
        phase.actions.append(result)
        logger.info("fix.ids: %s", "OK" if result.ok else f"FAILED - {result.data}")

        # Action 3: Fix headers
        result = await action_fix_headers(write=self.write)
        phase.actions.append(result)
        logger.info("fix.headers: %s", "OK" if result.ok else f"FAILED - {result.data}")

        # Action 4: Fix docstrings
        result = await action_fix_docstrings(
            core_context=self.core_context, write=self.write
        )
        phase.actions.append(result)
        logger.info(
            "fix.docstrings: %s", "OK" if result.ok else f"FAILED - {result.data}"
        )

        # Action 5: Fix logging
        result = await action_fix_logging(write=self.write)
        phase.actions.append(result)
        logger.info("fix.logging: %s", "OK" if result.ok else f"FAILED - {result.data}")

        self.result.phases.append(phase)
        logger.info(
            "Fix Phase complete: %d/%d actions succeeded",
            sum(1 for a in phase.actions if a.ok),
            len(phase.actions),
        )

    # ID: 56789012-3456-789a-bcde-f0123456789a
    async def _execute_sync_phase(self) -> None:
        """Execute all sync actions."""
        phase = WorkflowPhase(name="Sync State")
        logger.info("Starting Sync Phase")

        # Action 1: Sync to database
        result = await action_sync_database(
            core_context=self.core_context, write=self.write
        )
        phase.actions.append(result)
        logger.info("sync.db: %s", "OK" if result.ok else f"FAILED - {result.data}")

        # Action 2: Vectorize code (only if DB sync succeeded)
        if result.ok:
            result = await action_sync_code_vectors(
                core_context=self.core_context, write=self.write, force=False
            )
            phase.actions.append(result)
            logger.info(
                "sync.vectors.code: %s",
                "OK" if result.ok else f"FAILED - {result.data}",
            )
        else:
            logger.warning("Skipping code vectorization due to DB sync failure")

        # Action 3: Vectorize constitution (optional, only if write=True)
        # Skip if embedding settings not configured (this was the original issue)
        if self.write:
            try:
                result = await action_sync_constitutional_vectors(
                    core_context=self.core_context, write=self.write
                )
                phase.actions.append(result)
                logger.info(
                    "sync.vectors.constitution: %s",
                    "OK" if result.ok else f"FAILED - {result.data}",
                )
            except ValueError as e:
                # Missing embedding settings - log but don't fail
                logger.info(
                    "Skipping constitutional vectorization (settings not configured): %s",
                    e,
                )

        self.result.phases.append(phase)
        logger.info(
            "Sync Phase complete: %d/%d actions succeeded",
            sum(1 for a in phase.actions if a.ok),
            len(phase.actions),
        )
