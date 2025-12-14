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


# ID: 74616d91-8695-4792-bbda-d68d1a8f2b2e
class ReadFileHandler(ActionHandler):
    """Handles the 'read_file' action."""

    @property
    # ID: 63cfd73a-def4-4260-85d9-62c87915cee9
    def name(self) -> str:
        return "read_file"

    # ID: a481e567-0fb3-4bf5-be9f-3adb696bb0f1
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        full_path = resolve_target_path(params, context, must_exist=True)
        if full_path.is_dir():
            raise PlanExecutionError(
                f"Cannot read '{params.file_path}' because it is a directory."
            )
        content = full_path.read_text(encoding="utf-8")
        context.file_content_cache[params.file_path] = content
        logger.info("📖 Read file '%s' into context.", params.file_path)


# ID: 3f467788-baf7-4a68-adc1-6ba54e8a88e0
class ListFilesHandler(ActionHandler):
    """Handles the 'list_files' action."""

    @property
    # ID: cce3d0ca-759e-447a-a43d-f70153a84759
    def name(self) -> str:
        return "list_files"

    # ID: 76cff4bf-cf29-4814-9047-80eb2747d06b
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        full_path = resolve_target_path(params, context, must_exist=True)
        if not full_path.is_dir():
            raise PlanExecutionError(
                f"Directory to be listed does not exist or is not a directory: {params.file_path}"
            )
        contents = [item.name for item in full_path.iterdir()]
        context.file_content_cache[params.file_path] = "\n".join(sorted(contents))
        logger.info("📁 Listed contents of '%s' into context.", params.file_path)


# ID: 6cd5419f-acc0-4081-ab7d-3382414136e9
class DeleteFileHandler(ActionHandler):
    """Handles the 'delete_file' action."""

    @property
    # ID: da8616f9-8e66-4403-b370-bd117640ded5
    def name(self) -> str:
        return "delete_file"

    # ID: 15398f80-5c79-4e13-85f5-6c89a80997e0
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        try:
            full_path = resolve_target_path(params, context, must_exist=True)
            full_path.unlink()
            logger.info("🗑️  Deleted file: %s", params.file_path)
            if context.git_service.is_git_repo():
                context.git_service.add(params.file_path)
                context.git_service.commit(
                    f"refactor(cleanup): Remove obsolete file {params.file_path}"
                )
        except PlanExecutionError:
            logger.warning(
                "File '%s' to be deleted does not exist. Skipping.", params.file_path
            )
            return
