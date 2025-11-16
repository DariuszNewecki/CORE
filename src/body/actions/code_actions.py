# src/body/actions/code_actions.py

"""
Action handlers for complex code modification and creation.
"""

from __future__ import annotations

import ast
import textwrap

from shared.logger import getLogger
from shared.models import PlanExecutionError, TaskParams
from will.orchestration.validation_pipeline import validate_code_async

from .base import ActionHandler
from .context import PlanExecutorContext

logger = getLogger(__name__)


def _get_symbol_start_end_lines(
    tree: ast.AST, symbol_name: str
) -> tuple[int, int] | None:
    """Finds the 1-based start and end line numbers of a symbol."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol_name:
                if hasattr(node, "end_lineno") and node.end_lineno is not None:
                    return (node.lineno, node.end_lineno)
    return None


def _replace_symbol_in_code(
    original_code: str, symbol_name: str, new_code_str: str
) -> str:
    """
    Replaces a function/method in code with a new version using AST to find boundaries.
    """
    try:
        original_tree = ast.parse(original_code)
    except SyntaxError as e:
        raise ValueError(f"Could not parse original code due to syntax error: {e}")
    symbol_location = _get_symbol_start_end_lines(original_tree, symbol_name)
    if not symbol_location:
        raise ValueError(f"Symbol '{symbol_name}' not found in the original code.")
    start_line, end_line = symbol_location
    start_index = start_line - 1
    end_index = end_line
    lines = original_code.splitlines()
    original_symbol_line = lines[start_index]
    indentation = len(original_symbol_line) - len(original_symbol_line.lstrip(" "))
    clean_new_code = textwrap.dedent(new_code_str).strip()
    new_code_lines = [
        f"{' ' * indentation}{line}" for line in clean_new_code.splitlines()
    ]
    code_before = lines[:start_index]
    code_after = lines[end_index:]
    final_lines = code_before + new_code_lines + code_after
    return "\n".join(final_lines)


# ID: 631af2ad-29e0-4b41-9ef7-cc47bce5f1af
class CreateFileHandler(ActionHandler):
    """Handles the 'create_file' action."""

    @property
    # ID: 9aa848b9-144f-482e-8bc8-174bc60e8dec
    def name(self) -> str:
        return "create_file"

    # ID: 9074e95d-f6e1-4ae7-8e5d-acebf48d098c
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path, code = (params.file_path, params.code)
        if not all([file_path, code is not None]):
            raise PlanExecutionError(
                "Missing 'file_path' or 'code' for create_file action."
            )
        full_path = context.file_handler.repo_path / file_path
        if full_path.exists():
            raise FileExistsError(f"File '{file_path}' already exists.")
        validation_result = await validate_code_async(
            file_path, code, auditor_context=context.auditor_context
        )
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Generated code for '{file_path}' failed validation.",
                violations=validation_result["violations"],
            )
        context.file_handler.confirm_write(
            context.file_handler.add_pending_write(
                prompt=f"Goal: create file {file_path}",
                suggested_path=file_path,
                code=validation_result["code"],
            )
        )
        if context.git_service.is_git_repo():
            context.git_service.add(file_path)
            context.git_service.commit(f"feat: Create new file {file_path}")


# ID: f5fc09af-268c-4200-8b0b-e50d39006056
class EditFileHandler(ActionHandler):
    """Handles the 'edit_file' action."""

    @property
    # ID: 9a94ad58-913d-495a-802f-ba2944e2f3fe
    def name(self) -> str:
        return "edit_file"

    # ID: 6092b7c7-7367-4759-ab08-6938b16f2d3d
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path_str = params.file_path
        new_content = params.code
        if not all([file_path_str, new_content is not None]):
            raise PlanExecutionError(
                "Missing 'file_path' or 'code' for edit_file action."
            )
        full_path = context.file_handler.repo_path / file_path_str
        if not full_path.exists():
            raise PlanExecutionError(
                f"File to be edited does not exist: {file_path_str}"
            )
        validation_result = await validate_code_async(
            file_path_str, new_content, auditor_context=context.auditor_context
        )
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Generated code for '{file_path_str}' failed validation.",
                violations=validation_result["violations"],
            )
        context.file_handler.confirm_write(
            context.file_handler.add_pending_write(
                prompt=f"Goal: edit file {file_path_str}",
                suggested_path=file_path_str,
                code=validation_result["code"],
            )
        )
        if context.git_service.is_git_repo():
            context.git_service.add(file_path_str)
            context.git_service.commit(f"feat: Modify file {file_path_str}")


# ID: 15cf01e1-2c6c-491d-a3f5-c738ff6acf03
class EditFunctionHandler(ActionHandler):
    """Handles the 'edit_function' action."""

    @property
    # ID: c30f46c8-9016-426e-8ba0-1ac6339a4198
    def name(self) -> str:
        return "edit_function"

    # ID: b1407e7a-5034-4f46-be25-c1f7c1a017e8
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path, symbol_name, new_code = (
            params.file_path,
            params.symbol_name,
            params.code,
        )
        if not all([file_path, symbol_name, new_code is not None]):
            raise PlanExecutionError(
                "Missing required parameters for edit_function action."
            )
        full_path = context.file_handler.repo_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(
                f"Cannot edit function, file not found: '{file_path}'"
            )
        original_code = full_path.read_text("utf-8")
        validation_result = await validate_code_async(
            file_path, new_code, auditor_context=context.auditor_context
        )
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Generated code for '{symbol_name}' failed validation.",
                violations=validation_result["violations"],
            )
        validated_code_snippet = validation_result["code"]
        try:
            final_code = _replace_symbol_in_code(
                original_code, symbol_name, validated_code_snippet
            )
        except ValueError as e:
            raise PlanExecutionError(f"Failed to edit code in '{file_path}': {e}")
        context.file_handler.confirm_write(
            context.file_handler.add_pending_write(
                prompt=f"Goal: edit function {symbol_name} in {file_path}",
                suggested_path=file_path,
                code=final_code,
            )
        )
        if context.git_service.is_git_repo():
            context.git_service.add(file_path)
            context.git_service.commit(
                f"feat: Modify function {symbol_name} in {file_path}"
            )
