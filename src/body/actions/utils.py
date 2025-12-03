# src/body/actions/utils.py
"""
Shared utilities for ActionHandlers to reduce duplication in path resolution and validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from shared.models import PlanExecutionError

if TYPE_CHECKING:
    from shared.models import TaskParams

    from .context import PlanExecutorContext


# ID: cdc9d705-4fcc-4856-b8f5-a35b55cd2b5b
def resolve_target_path(
    params: TaskParams,
    context: PlanExecutorContext,
    must_exist: bool = False,
    must_not_exist: bool = False,
) -> Path:
    """
    Resolves the 'file_path' from params relative to the repository root in context.
    Performs standard validation checks.

    Args:
        params: The task parameters containing 'file_path'.
        context: The execution context containing 'file_handler' (repo_path).
        must_exist: If True, raises PlanExecutionError if file does not exist.
        must_not_exist: If True, raises FileExistsError if file already exists.

    Returns:
        The resolved absolute Path.

    Raises:
        PlanExecutionError: If parameters are missing or validation fails.
        FileExistsError: If must_not_exist is True and file exists.
    """
    file_path_str = params.file_path
    if not file_path_str:
        raise PlanExecutionError("Missing 'file_path' parameter.")

    full_path = context.file_handler.repo_path / file_path_str

    if must_exist and not full_path.exists():
        raise PlanExecutionError(f"Target path does not exist: {file_path_str}")

    if must_not_exist and full_path.exists():
        raise FileExistsError(f"File '{file_path_str}' already exists.")

    return full_path
