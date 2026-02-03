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

from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger
from shared.models.workflow_models import WorkflowPhase, WorkflowResult


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: class-dev-sync-workflow
# ID: b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e
class DevSyncWorkflow:
    """
    Constitutional orchestration of the dev-sync workflow.

    Phases:
    1. Fix Phase: Make code constitutional (format, lint, headers)
    2. Sync Phase: Propagate clean state (database sync, vectorization)

    Constitutional Compliance:
    - All actions routed through ActionExecutor
    - Full audit trail via ActionResult
    - Automatic dependency injection via CoreContext
    - Governed file operations
    """

    def __init__(self, context: CoreContext):
        """
        Initialize workflow with constitutional context.

        Args:
            context: CoreContext providing governed capabilities
        """
        self.context = context
        self.executor = ActionExecutor(context)

    # ID: method-run
    # ID: c2d3e4f5-6a7b-8c9d-0e1f-2a3b4c5d6e7f
    async def run(self) -> WorkflowResult:
        """
        Execute the complete dev-sync workflow.

        Returns:
            WorkflowResult with all phase results and audit trail
        """
        logger.info("🚀 Starting dev-sync workflow...")

        result = WorkflowResult(workflow_id="dev_sync")

        # Phase 1: Fix
        fix_phase = await self._run_fix_phase()
        result.phases.append(fix_phase)

        if not fix_phase.ok:
            logger.warning("❌ Fix phase failed, skipping sync phase")
            return result

        # Phase 2: Sync
        sync_phase = await self._run_sync_phase()
        result.phases.append(sync_phase)

        if result.ok:
            logger.info("✅ Dev-sync workflow completed successfully")
        else:
            logger.warning("⚠️  Dev-sync workflow completed with failures")

        return result

    # ID: method-run-fix-phase
    # ID: d3e4f5a6-7b8c-9d0e-1f2a-3b4c5d6e7f8a
    async def _run_fix_phase(self) -> WorkflowPhase:
        """
        Phase 1: Make code constitutional.

        Actions:
        - fix_ids: Ensure all symbols have constitutional IDs
        - add_docstrings: Add missing docstrings
        - format_code: Apply Black formatting
        - lint_code: Apply Ruff fixes

        Returns:
            WorkflowPhase with all fix action results
        """
        phase = WorkflowPhase(name="fix")

        logger.info("📝 Phase 1: Fix")

        # Action 1: Fix IDs
        fix_ids_result = await self.executor.execute_action(
            action_name="fix_ids",
            action_params={},
        )
        phase.actions.append(fix_ids_result)

        if not fix_ids_result.ok:
            logger.warning("⚠️  fix_ids failed, continuing anyway")

        # Action 2: Add docstrings
        docstring_result = await self.executor.execute_action(
            action_name="add_docstrings",
            action_params={},
        )
        phase.actions.append(docstring_result)

        if not docstring_result.ok:
            logger.warning("⚠️  add_docstrings failed, continuing anyway")

        # Action 3: Format code
        format_result = await self.executor.execute_action(
            action_name="format_code",
            action_params={},
        )
        phase.actions.append(format_result)

        if not format_result.ok:
            logger.warning("⚠️  format_code failed, continuing anyway")

        # Action 4: Lint code
        lint_result = await self.executor.execute_action(
            action_name="lint_code",
            action_params={},
        )
        phase.actions.append(lint_result)

        if not lint_result.ok:
            logger.warning("⚠️  lint_code failed")

        return phase

    # ID: method-run-sync-phase
    # ID: e4f5a6b7-8c9d-0e1f-2a3b-4c5d6e7f8a9b
    async def _run_sync_phase(self) -> WorkflowPhase:
        """
        Phase 2: Propagate clean state to database and vectors.

        Actions:
        - sync_database: Update symbol metadata in database
        - vectorize: Generate and store embeddings

        Returns:
            WorkflowPhase with all sync action results
        """
        phase = WorkflowPhase(name="sync")

        logger.info("🔄 Phase 2: Sync")

        # Action 1: Sync database
        db_sync_result = await self.executor.execute_action(
            action_name="sync_database",
            action_params={},
        )
        phase.actions.append(db_sync_result)

        if not db_sync_result.ok:
            logger.error("❌ sync_database failed, skipping vectorization")
            return phase

        # Action 2: Vectorize
        vectorize_result = await self.executor.execute_action(
            action_name="vectorize",
            action_params={},
        )
        phase.actions.append(vectorize_result)

        if not vectorize_result.ok:
            logger.error("❌ vectorize failed")

        return phase
