# src/body/actions/healing_actions.py
"""
Action handlers for autonomous self-healing capabilities.
"""

from __future__ import annotations

from body.actions.base import ActionHandler
from body.actions.context import PlanExecutorContext
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import _async_fix_docstrings
from features.self_healing.header_service import _run_header_fix_cycle
from shared.config import settings
from shared.models import TaskParams


# ID: 79845741-cb28-483e-a017-1f962570f1fa
class FixDocstringsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_docstrings' action."""

    @property
    # ID: 36fd4346-26f4-4fce-97dd-8ff24ceb4bc3
    def name(self) -> str:
        """Return the unique identifier for this self-healing module."""
        return "autonomy.self_healing.fix_docstrings"

    # ID: 098a9dcb-dab9-40df-9ef7-150fd21c5770
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """
        Executes the docstring fixing logic by calling the dedicated service.
        This action does not run in dry-run mode; it always applies changes.
        """
        await _async_fix_docstrings(dry_run=False)


# ID: 229e24e4-67d0-4e63-a610-42858e150ac3
class FixHeadersHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_headers' action."""

    @property
    # ID: 4512e458-3548-4932-982c-71793d166c00
    def name(self) -> str:
        return "autonomy.self_healing.fix_headers"

    # ID: 4828affd-f7da-4995-9493-70372f11a144
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Executes the header fixing logic for all Python files."""
        src_dir = settings.REPO_PATH / "src"
        all_py_files = [
            str(p.relative_to(settings.REPO_PATH)) for p in src_dir.rglob("*.py")
        ]
        _run_header_fix_cycle(dry_run=False, all_py_files=all_py_files)


# ID: 363fd253-58df-4603-877c-03cffdc626b1
class FormatCodeHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.format_code' action."""

    @property
    # ID: b90e14b5-7741-4e86-8451-2682c10718f0
    def name(self) -> str:
        return "autonomy.self_healing.format_code"

    # ID: 4f311df7-b97a-4a9c-ab54-1369ec41988e
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Executes the code formatting logic by calling the dedicated service."""
        # --- START MODIFICATION ---
        # The handler now passes the file_path from the plan to the service.
        # If no file_path is provided, it defaults to the old behavior.
        format_code(path=params.file_path)
        # --- END MODIFICATION ---
