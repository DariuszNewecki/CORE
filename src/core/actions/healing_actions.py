# src/core/actions/healing_actions.py
"""
Action handlers for autonomous self-healing capabilities.
"""

from __future__ import annotations

from core.actions.base import ActionHandler
from core.actions.context import PlanExecutorContext
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import _async_fix_docstrings
from features.self_healing.header_service import _run_header_fix_cycle
from shared.config import settings
from shared.models import TaskParams


# ID: 57591e08-9aab-478a-8f56-3a0c7d618064
class FixDocstringsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_docstrings' action."""

    @property
    # ID: d8fa2ec9-da57-40f0-b3e8-8832332f63c7
    def name(self) -> str:
        """Return the unique identifier for this self-healing module."""
        return "autonomy.self_healing.fix_docstrings"

    # ID: 83bfe85a-6373-4983-8fe1-62104fa1f1e5
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """
        Executes the docstring fixing logic by calling the dedicated service.
        This action does not run in dry-run mode; it always applies changes.
        """
        await _async_fix_docstrings(dry_run=False)


# ID: 49d5aa15-85f9-4ca1-93c9-fb84c7bcfa37
class FixHeadersHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_headers' action."""

    @property
    # ID: 86350ba5-ef05-4a15-8e4e-7a6dbe83c549
    def name(self) -> str:
        return "autonomy.self_healing.fix_headers"

    # ID: ea34f0f1-f8f6-4f58-934d-6f9512a023a6
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
        format_code()
