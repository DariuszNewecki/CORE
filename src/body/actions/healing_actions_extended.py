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


# ID: e0db6619-74fe-42dc-af04-b209f047bc34
class FixUnusedImportsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_imports' action."""

    @property
    # ID: ed495f91-3d7e-4a43-ba1b-4b130ff2691f
    def name(self) -> str:
        return "autonomy.self_healing.fix_imports"

    # ID: a93c2b29-4d68-4e28-ab39-6995010099c8
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Removes unused imports using ruff via the sanctioned linter service."""
        target_path = params.file_path or "src/"
        try:
            run_poetry_command(
                f"Fixing unused imports in {target_path}",
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
            logger.info("Fixed unused imports in %s", target_path)
        except Exception as e:
            logger.error("Failed to fix imports: %s", e)
            raise


# ID: 4d3424b8-7a82-42a3-b0b9-bc904516e68b
class RemoveDeadCodeHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.remove_dead_code' action."""

    @property
    # ID: 3d8a8c30-07c8-4ce8-84ab-3117e529327b
    def name(self) -> str:
        return "autonomy.self_healing.remove_dead_code"

    # ID: e5388c75-452e-4d9e-8ff5-87e4fa9afd6e
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Removes unreachable code using ruff via the sanctioned linter service."""
        target_path = params.file_path or "src/"
        try:
            run_poetry_command(
                f"Removing dead code in {target_path}",
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
            logger.info("Removed dead code in %s", target_path)
        except Exception as e:
            logger.error("Failed to remove dead code: %s", e)
            raise


# ID: 20798537-ddac-4b71-91b6-c0f4365d3b7e
class EnforceLineLengthHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_line_length' action."""

    @property
    # ID: 30f35751-59ff-439f-92bb-f0d890ca0a69
    def name(self) -> str:
        return "autonomy.self_healing.fix_line_length"

    # ID: c63f6873-e502-4742-92a8-60fe07f79fc8
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Enforces line length limit using existing service."""
        from features.self_healing.linelength_service import _async_fix_line_lengths

        target_path = params.file_path
        if target_path:
            files_to_fix = [Path(settings.REPO_PATH) / target_path]
        else:
            src_dir = settings.REPO_PATH / "src"
            files_to_fix = list(src_dir.rglob("*.py"))
        try:
            await _async_fix_line_lengths(files_to_fix, dry_run=False)
            logger.info(f"Fixed line lengths in {len(files_to_fix)} files")
        except Exception as e:
            logger.error("Failed to fix line lengths: %s", e)
            raise


# ID: 339be393-24de-4c3b-b808-096b277496a9
class AddPolicyIDsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.add_policy_ids' action."""

    @property
    # ID: f2704a83-05b9-4f10-b8be-1d8157b9327c
    def name(self) -> str:
        return "autonomy.self_healing.add_policy_ids"

    # ID: 202434d6-46d1-4caf-a1e9-62e4d57bcb7c
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Adds missing UUIDs to policy files using existing service."""
        from features.self_healing.policy_id_service import add_missing_policy_ids

        try:
            count = add_missing_policy_ids(dry_run=False)
            logger.info("Added policy IDs to %s files", count)
        except Exception as e:
            logger.error("Failed to add policy IDs: %s", e)
            raise


# ID: a505cf51-1aa3-4be5-92c2-b496d702d200
class SortImportsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.sort_imports' action."""

    @property
    # ID: 79e5f989-1b8d-42c6-9d5a-63c165f60602
    def name(self) -> str:
        return "autonomy.self_healing.sort_imports"

    # ID: fd4ca499-e735-41c7-b220-5e11a05e8323
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Sorts imports according to style policy using ruff via the sanctioned linter service."""
        target_path = params.file_path or "src/"
        try:
            run_poetry_command(
                f"Sorting imports in {target_path}",
                ["ruff", "check", target_path, "--fix", "--select", "I", "--exit-zero"],
            )
            logger.info("Sorted imports in %s", target_path)
        except Exception as e:
            logger.error("Failed to sort imports: %s", e)
            raise
