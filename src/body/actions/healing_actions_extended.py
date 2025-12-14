# src/body/actions/healing_actions_extended.py

"""
Extended action handlers for autonomous self-healing capabilities.
"""

from __future__ import annotations

from pathlib import Path

from body.actions.base import ActionHandler
from body.actions.context import PlanExecutorContext
from shared.config import settings
from shared.logger import getLogger
from shared.models import TaskParams
from shared.utils.subprocess_utils import run_poetry_command


logger = getLogger(__name__)


# ID: f8eb9212-6de9-40a0-b8cb-d24b0e070c99
class FixUnusedImportsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_imports' action."""

    @property
    # ID: 13174a6a-53b2-4842-8f7c-b4825e6d71b7
    def name(self) -> str:
        return "autonomy.self_healing.fix_imports"

    # ID: 5707c979-4387-4aed-8fc5-d4b8d76177ec
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Removes unused imports using ruff via the sanctioned linter service."""
        target_path = params.file_path or "src/"
        logger.info("🔄 Starting unused import cleanup in %s", target_path)
        try:
            run_poetry_command(
                "",  # Removed UI progress string — now silent + logged
                [
                    "ruff",
                    "check",
                    target_path,
                    "--fix",
                    "--select",
                    "F401",
                    "--exit-zero",
                ],
            )
            logger.info("✅ Fixed unused imports in %s", target_path)
        except Exception as e:
            logger.error("Failed to fix imports: %s", e)
            raise


# ID: 359cd37f-b375-4527-8225-27bb4b2a2dd4
class RemoveDeadCodeHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.remove_dead_code' action."""

    @property
    # ID: 99bb6e53-b777-4b73-894f-8414ee878fd0
    def name(self) -> str:
        return "autonomy.self_healing.remove_dead_code"

    # ID: 8ab547f6-f904-4277-b9ae-5dc3305696f6
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Removes unreachable code using ruff via the sanctioned linter service."""
        target_path = params.file_path or "src/"
        logger.info("🔄 Starting dead code removal in %s", target_path)
        try:
            run_poetry_command(
                "",  # Removed UI progress string
                [
                    "ruff",
                    "check",
                    target_path,
                    "--fix",
                    "--select",
                    "F401,F841",
                    "--exit-zero",
                ],
            )
            logger.info("✅ Removed dead code in %s", target_path)
        except Exception as e:
            logger.error("Failed to remove dead code: %s", e)
            raise


# ID: 5a5a4107-2176-4eee-8009-43b694d90e79
class EnforceLineLengthHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_line_length' action."""

    @property
    # ID: 327aa8c6-4278-4787-ad38-f5a3975190aa
    def name(self) -> str:
        return "autonomy.self_healing.fix_line_length"

    # ID: 651596fc-aa1c-4aa0-ab49-a49f2106b788
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Enforces line length limit using existing service."""
        from features.self_healing.linelength_service import _async_fix_line_lengths

        target_path = params.file_path
        if target_path:
            files_to_fix = [Path(settings.REPO_PATH) / target_path]
            logger.info("🔄 Enforcing line length in specific file: %s", target_path)
        else:
            src_dir = settings.REPO_PATH / "src"
            files_to_fix = list(src_dir.rglob("*.py"))
            logger.info(
                "🔄 Enforcing line length across all %s Python files", len(files_to_fix)
            )
        try:
            await _async_fix_line_lengths(files_to_fix, dry_run=False)
            logger.info(
                "✅ Line length enforcement completed (%s files)", len(files_to_fix)
            )
        except Exception as e:
            logger.error("Failed to fix line lengths: %s", e)
            raise


# ID: 1a87107a-3285-4379-a4c1-99759e6008da
class AddPolicyIDsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.add_policy_ids' action."""

    @property
    # ID: 7361de44-485b-4840-8523-1f216eeda664
    def name(self) -> str:
        return "autonomy.self_healing.add_policy_ids"

    # ID: 21ff3678-1432-456e-9c2d-f631381247fe
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Adds missing UUIDs to policy files using existing service."""
        from features.self_healing.policy_id_service import add_missing_policy_ids

        logger.info("🔄 Starting policy ID addition cycle...")
        try:
            count = add_missing_policy_ids(dry_run=False)
            logger.info("✅ Added policy IDs to %s files", count)
        except Exception as e:
            logger.error("Failed to add policy IDs: %s", e)
            raise


# ID: 3b1881df-c5e9-495a-9d27-372a0e9b93ef
class SortImportsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.sort_imports' action."""

    @property
    # ID: 9d2a1ed7-a022-42ce-9cba-517a744ed059
    def name(self) -> str:
        return "autonomy.self_healing.sort_imports"

    # ID: c5e0961f-968f-4613-9fe3-dfb2b8ef13a0
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Sorts imports according to style policy using ruff via the sanctioned linter service."""
        target_path = params.file_path or "src/"
        logger.info("🔄 Starting import sorting in %s", target_path)
        try:
            run_poetry_command(
                "",  # Removed UI progress string
                ["ruff", "check", target_path, "--fix", "--select", "I", "--exit-zero"],
            )
            logger.info("✅ Sorted imports in %s", target_path)
        except Exception as e:
            logger.error("Failed to sort imports: %s", e)
            raise
