# src/core/actions/code_actions.py
"""
Action handlers for complex code modification and creation.
"""
from __future__ import annotations

import ast
import textwrap
from typing import Optional, Tuple

from core.validation_pipeline import validate_code_async
from shared.logger import getLogger
from shared.models import PlanExecutionError, TaskParams

from .base import ActionHandler
from .context import PlanExecutorContext

log = getLogger("code_actions")


# --- START: Logic moved from the deleted CodeEditor class ---
def _get_symbol_start_end_lines(
    tree: ast.AST, symbol_name: str
) -> Optional[Tuple[int, int]]:
    """Finds the 1-based start and end line numbers of a symbol."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol_name:
                # ast.get_source_segment is more reliable if end_lineno is available
                if hasattr(node, "end_lineno") and node.end_lineno is not None:
                    return node.lineno, node.end_lineno
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

    # Determine indentation from the first line of the original symbol
    original_symbol_line = lines[start_index]
    indentation = len(original_symbol_line) - len(original_symbol_line.lstrip(" "))

    # Dedent and re-indent the new code to match the original's indentation
    clean_new_code = textwrap.dedent(new_code_str).strip()
    new_code_lines = [
        f"{' ' * indentation}{line}" for line in clean_new_code.splitlines()
    ]

    code_before = lines[:start_index]
    code_after = lines[end_index:]

    final_lines = code_before + new_code_lines + code_after
    return "\n".join(final_lines)


# --- END: Logic moved from the deleted CodeEditor class ---


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9c0d
# ID: 2b764ba7-4bf1-4827-9c47-bec092758cb8
class CreateFileHandler(ActionHandler):
    """Handles the 'create_file' action."""

    @property
    # ID: f650040b-ce19-4663-ab49-3943d3dcca20
    def name(self) -> str:
        return "create_file"

    # ID: 9bd3f774-d4f8-4bc0-93f3-c604742dfe0a
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        file_path, code = params.file_path, params.code
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


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c
# ID: a0a1f246-224f-4881-b0f1-2cfda08a40ac
class EditFileHandler(ActionHandler):
    """Handles the 'edit_file' action."""

    @property
    # ID: 3fc89f7f-c949-4f11-a3ff-ac0ac96795a1
    def name(self) -> str:
        return "edit_file"

    # ID: b6502a6e-c6f5-4fc1-9ad4-21c06ba16b3a
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


# ID: 0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
class EditFunctionHandler(ActionHandler):
    """Handles the 'edit_function' action."""

    @property
    # ID: 2b2a9ab6-ebd5-4846-8165-e796c851b6e2
    def name(self) -> str:
        return "edit_function"

    # ID: 4ca616d7-7ffb-4b3c-acbb-fd6a089e612c
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

        # First, validate the new code snippet in isolation
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
