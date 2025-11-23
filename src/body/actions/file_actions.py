# src/body/actions/file_actions.py

"""
Action handlers for basic file system operations like read, list, and delete.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.models import PlanExecutionError, TaskParams

from .base import ActionHandler
from .context import PlanExecutorContext

logger = getLogger(__name__)


# ID: 84ed29ab-f969-4780-a869-d33b6b1a52f6
class ReadFileHandler(ActionHandler):
    """Handles the 'read_file' action."""

    @property
    # ID: 66f15ecb-b0f2-4d55-a76f-57c729e22a41
    def name(self) -> str:
        return "read_file"

    # ID: 929331f5-b276-43e4-afc3-cef0b335b60b
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
        logger.info(f"📖 Read file '{file_path_str}' into context.")


# ID: 2bf03b98-bbc0-4629-aa64-c685bfb20233
class ListFilesHandler(ActionHandler):
    """Handles the 'list_files' action."""

    @property
    # ID: 9ee2b33e-607d-4248-aa4e-9afe8c32aabd
    def name(self) -> str:
        return "list_files"

    # ID: 9aeae6e3-5652-4a99-9eb0-960dba19285b
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
        logger.info(f"📁 Listed contents of '{dir_path_str}' into context.")


# ID: 066fd67e-dc38-4138-a878-8ce1f51fd8e4
class DeleteFileHandler(ActionHandler):
    """Handles the 'delete_file' action."""

    @property
    # ID: c4995027-f6d8-47a9-82f9-bd301213d283
    def name(self) -> str:
        return "delete_file"

    # ID: eaa645b5-8676-4fd4-afa2-9527707808de
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path_str = params.file_path
        if not file_path_str:
            raise PlanExecutionError("Missing 'file_path' for delete_file action.")
        full_path = context.file_handler.repo_path / file_path_str
        if not full_path.exists():
            logger.warning(
                f"File '{file_path_str}' to be deleted does not exist. Skipping."
            )
            return
        full_path.unlink()
        logger.info(f"🗑️  Deleted file: {file_path_str}")
        if context.git_service.is_git_repo():
            context.git_service.add(file_path_str)
            context.git_service.commit(
                f"refactor(cleanup): Remove obsolete file {file_path_str}"
            )
