# src/agents/plan_executor.py
"""
Intent: Provides a dedicated, atomic service for executing a pre-defined plan.

This module separates the execution logic from the planning and generation logic
of the PlannerAgent, adhering to the 'separation_of_concerns' principle.
"""
import asyncio
from typing import List

from core.file_handler import FileHandler
from core.git_service import GitService
from core.validation_pipeline import validate_code
from shared.logger import getLogger

from agents.models import ExecutionTask, PlannerConfig, TaskParams
from agents.utils import CodeEditor, SymbolLocator

log = getLogger(__name__)


class PlanExecutionError(Exception):
    """Custom exception for failures during plan execution."""

    def __init__(self, message, violations=None):
        super().__init__(message)
        self.violations = violations or []


class PlanExecutor:
    """A service that takes a list of ExecutionTasks and executes them sequentially."""

    def __init__(
        self, file_handler: FileHandler, git_service: GitService, config: PlannerConfig
    ):
        """Initializes the executor with necessary dependencies."""
        self.file_handler = file_handler
        self.git_service = git_service
        self.config = config
        self.repo_path = self.file_handler.repo_path
        self.symbol_locator = SymbolLocator()
        self.code_editor = CodeEditor()
        self._executor = asyncio.get_event_loop().run_in_executor

    async def execute_plan(self, plan: List[ExecutionTask]):
        """Executes the entire plan, one task at a time."""
        for i, task in enumerate(plan, 1):
            log.info(f"--- Executing Step {i}/{len(plan)}: {task.step} ---")
            await self._execute_task_with_timeout(task)

    async def _execute_task_with_timeout(self, task: ExecutionTask):
        """Execute task with timeout protection."""
        timeout = self.config.task_timeout
        try:
            await asyncio.wait_for(self._execute_task(task), timeout=timeout)
        except asyncio.TimeoutError:
            raise PlanExecutionError(f"Task '{task.step}' timed out after {timeout}s")

    async def _execute_task(self, task: ExecutionTask):
        """Dispatcher that executes a single task from a plan based on its action type."""
        action_map = {
            "add_capability_tag": self._execute_add_tag,
            "create_file": self._execute_create_file,
            "edit_function": self._execute_edit_function,
        }
        if task.action in action_map:
            await action_map[task.action](task.params)
        else:
            log.warning(f"Skipping task: Unknown action '{task.action}'.")

    async def _execute_add_tag(self, params: TaskParams):
        """Executes the surgical 'add_capability_tag' action."""
        file_path, symbol_name, tag = params.file_path, params.symbol_name, params.tag
        line_number = await self._executor(
            None,
            self.symbol_locator.find_symbol_line,
            self.repo_path / file_path,
            symbol_name,
        )
        if not line_number:
            raise PlanExecutionError(
                f"Could not find symbol '{symbol_name}' in '{file_path}'."
            )

        full_path = self.repo_path / file_path
        if not full_path.exists():
            raise PlanExecutionError(f"File '{file_path}' does not exist.")

        lines = full_path.read_text(encoding="utf-8").splitlines()

        insertion_index = line_number - 1
        indentation = len(lines[insertion_index]) - len(
            lines[insertion_index].lstrip(" ")
        )
        lines.insert(insertion_index, f"{' ' * indentation}# CAPABILITY: {tag}")
        modified_code = "\n".join(lines)

        validation_result = validate_code(file_path, modified_code)
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Surgical modification for '{file_path}' failed validation.",
                violations=validation_result["violations"],
            )

        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: add tag to {symbol_name}",
            suggested_path=file_path,
            code=validation_result["code"],
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(
                f"refactor(capability): Add '{tag}' tag to {symbol_name}"
            )

    async def _execute_create_file(self, params: TaskParams):
        """Executes the 'create_file' action."""
        file_path, code = params.file_path, params.code
        full_path = self.repo_path / file_path
        if full_path.exists():
            raise FileExistsError(
                f"File '{file_path}' already exists. Use 'edit_function' instead."
            )

        validation_result = validate_code(file_path, code)
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Generated code for '{file_path}' failed validation.",
                violations=validation_result["violations"],
            )

        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: create file {file_path}",
            suggested_path=file_path,
            code=validation_result["code"],
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(f"feat: Create new file {file_path}")

    async def _execute_edit_function(self, params: TaskParams):
        """Executes the 'edit_function' action using the CodeEditor."""
        file_path, symbol_name, new_code = (
            params.file_path,
            params.symbol_name,
            params.code,
        )
        full_path = self.repo_path / file_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"Cannot edit function, file not found: '{file_path}'"
            )

        original_code = await self._executor(None, full_path.read_text, "utf-8")

        validation_result = validate_code(file_path, new_code)
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Generated code for '{symbol_name}' failed validation.",
                violations=validation_result["violations"],
            )

        validated_code_snippet = validation_result["code"]
        try:
            final_code = self.code_editor.replace_symbol_in_code(
                original_code, symbol_name, validated_code_snippet
            )
        except ValueError as e:
            raise PlanExecutionError(f"Failed to edit code in '{file_path}': {e}")

        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: edit function {symbol_name} in {file_path}",
            suggested_path=file_path,
            code=final_code,
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(
                f"feat: Modify function {symbol_name} in {file_path}"
            )
