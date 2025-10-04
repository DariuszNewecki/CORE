# src/core/actions/file_actions.py
"""
Action handlers for basic file system operations like read, list, and delete.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.models import PlanExecutionError, TaskParams

from .base import ActionHandler
from .context import PlanExecutorContext

log = getLogger("file_actions")


# ID: 3c4d5e6f-7a8b-9c0d-1e2f3a4b5c6d
# ID: c058bf71-924a-497a-8847-449129f96068
class ReadFileHandler(ActionHandler):
    """Handles the 'read_file' action."""

    @property
    # ID: bf0bc446-13a0-4e3e-bbd2-cb6eecc43cab
    def name(self) -> str:
        return "read_file"

    # ID: dbb82014-953a-4832-b0ee-97bd19f348a9
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path_str = params.file_path
        if not file_path_str:
            raise PlanExecutionError("Missing 'file_path' for read_file action.")

        full_path = context.file_handler.repo_path / file_path_str
        if not full_path.exists():
            raise PlanExecutionError(f"File to be read does not exist: {file_path_str}")

        if full_path.is_dir():
            raise PlanExecutionError(
                f"Cannot read '{file_path_str}' because it is a directory."
            )

        content = full_path.read_text(encoding="utf-8")
        context.file_content_cache[file_path_str] = content
        log.info(f"📖 Read file '{file_path_str}' into context.")


# ID: 5e6f7a8b-9c0d-1e2f-3a4b5c6d7f8a
# ID: 90e3703f-1c72-402e-b904-96f0e6341059
class ListFilesHandler(ActionHandler):
    """Handles the 'list_files' action."""

    @property
    # ID: 9d607637-7e59-4c84-9b1b-e7f9097fd066
    def name(self) -> str:
        return "list_files"

    # ID: 497141ed-5562-4b14-a9b9-94cfb09b16e9
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        dir_path_str = params.file_path
        if not dir_path_str:
            raise PlanExecutionError("Missing 'file_path' for list_files action.")

        full_path = context.file_handler.repo_path / dir_path_str
        if not full_path.is_dir():
            raise PlanExecutionError(
                f"Directory to be listed does not exist or is not a directory: {dir_path_str}"
            )

        contents = [item.name for item in full_path.iterdir()]
        context.file_content_cache[dir_path_str] = "\n".join(sorted(contents))
        log.info(f"📁 Listed contents of '{dir_path_str}' into context.")


# ID: 6f7a8b9c-0d1e-2f3a-4b5c6d7e8f9b
# ID: 7dbbbc26-0dd4-4c3e-8938-dd6ba3c715b0
class DeleteFileHandler(ActionHandler):
    """Handles the 'delete_file' action."""

    @property
    # ID: dc164637-5cf6-4999-880b-076db48e7b29
    def name(self) -> str:
        return "delete_file"

    # ID: e7de77a8-59e5-4b53-85ef-1c8a9c893202
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path_str = params.file_path
        if not file_path_str:
            raise PlanExecutionError("Missing 'file_path' for delete_file action.")

        full_path = context.file_handler.repo_path / file_path_str
        if not full_path.exists():
            log.warning(
                f"File '{file_path_str}' to be deleted does not exist. Skipping."
            )
            return

        full_path.unlink()
        log.info(f"🗑️  Deleted file: {file_path_str}")

        if context.git_service.is_git_repo():
            context.git_service.add(file_path_str)  # Stage the deletion
            context.git_service.commit(
                f"refactor(cleanup): Remove obsolete file {file_path_str}"
            )
