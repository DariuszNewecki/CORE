# src/body/actions/file_actions.py

"""
Action handlers for basic file system operations like read, list, and delete.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.models import PlanExecutionError, TaskParams

from .base import ActionHandler
from .context import PlanExecutorContext
from .utils import resolve_target_path


logger = getLogger(__name__)


# ID: 4088cf99-3f53-49d7-b8b3-20a0ab5189b4
class ReadFileHandler(ActionHandler):
    """Handles the 'read_file' action."""

    @property
    # ID: 2d0a9ec8-2088-43d5-8c17-3a509dd39576
    def name(self) -> str:
        return "read_file"

    # ID: 26cab27f-86ba-4f03-91ca-72275ab9c5d7
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        # Enforce existence check here
        full_path = resolve_target_path(params, context, must_exist=True)

        if full_path.is_dir():
            raise PlanExecutionError(
                f"Cannot read '{params.file_path}' because it is a directory."
            )

        content = full_path.read_text(encoding="utf-8")
        context.file_content_cache[params.file_path] = content
        logger.info(f"📖 Read file '{params.file_path}' into context.")


# ID: 47e13615-767e-4eea-80c6-5e7f08d22638
class ListFilesHandler(ActionHandler):
    """Handles the 'list_files' action."""

    @property
    # ID: 54a48f16-7e03-4e84-b859-98714e288ce3
    def name(self) -> str:
        return "list_files"

    # ID: fc084385-c88a-4efe-b780-971248bfbb9b
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        # Enforce existence check here
        full_path = resolve_target_path(params, context, must_exist=True)

        if not full_path.is_dir():
            raise PlanExecutionError(
                f"Directory to be listed does not exist or is not a directory: {params.file_path}"
            )

        contents = [item.name for item in full_path.iterdir()]
        context.file_content_cache[params.file_path] = "\n".join(sorted(contents))
        logger.info(f"📁 Listed contents of '{params.file_path}' into context.")


# ID: 74439849-ff1a-443f-9669-545a60e267f0
class DeleteFileHandler(ActionHandler):
    """Handles the 'delete_file' action."""

    @property
    # ID: d18e067e-e0b6-408e-b0ca-463b43d1a216
    def name(self) -> str:
        return "delete_file"

    # ID: ec26816c-2d56-45ff-b8e5-caea8a57a4d9
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        try:
            # We use must_exist=True so we can catch the specific case where it's missing
            # and log the warning, matching original behavior.
            full_path = resolve_target_path(params, context, must_exist=True)

            full_path.unlink()
            logger.info(f"🗑️  Deleted file: {params.file_path}")

            if context.git_service.is_git_repo():
                context.git_service.add(params.file_path)
                context.git_service.commit(
                    f"refactor(cleanup): Remove obsolete file {params.file_path}"
                )

        except PlanExecutionError:
            # Original behavior: Warn but do not fail if file doesn't exist
            logger.warning(
                f"File '{params.file_path}' to be deleted does not exist. Skipping."
            )
            return
