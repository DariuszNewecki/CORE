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


class FixDocstringsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_docstrings' action."""

    @property
    def name(self) -> str:
        """Return the unique identifier for this self-healing module."""
        return "autonomy.self_healing.fix_docstrings"

    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """
        Executes the docstring fixing logic by calling the dedicated service.
        This action does not run in dry-run mode; it always applies changes.
        """
        await _async_fix_docstrings(dry_run=False)


class FixHeadersHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_headers' action."""

    @property
    def name(self) -> str:
        return "autonomy.self_healing.fix_headers"

    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Executes the header fixing logic for all Python files."""
        src_dir = settings.REPO_PATH / "src"
        all_py_files = [
            str(p.relative_to(settings.REPO_PATH)) for p in src_dir.rglob("*.py")
        ]
        _run_header_fix_cycle(dry_run=False, all_py_files=all_py_files)


class FormatCodeHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.format_code' action."""

    @property
    def name(self) -> str:
        return "autonomy.self_healing.format_code"

    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """Executes the code formatting logic by calling the dedicated service."""
        format_code()
