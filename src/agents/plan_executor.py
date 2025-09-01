# src/agents/plan_executor.py
"""
Executes a sequence of predefined code modification tasks including file creation, function editing, capability tagging, and proposal generation.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import List

import yaml

from agents.models import ExecutionTask, PlannerConfig, TaskParams
from agents.utils import CodeEditor, SymbolLocator
from core.file_handler import FileHandler
from core.git_service import GitService
from core.validation_pipeline import validate_code
from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: agent.plan.error
class PlanExecutionError(Exception):
    """Custom exception for failures during plan execution."""

    def __init__(self, message, violations=None):
        super().__init__(message)
        self.violations = violations or []


# CAPABILITY: agent.plan.execute
class PlanExecutor:
    """A service that takes a list of ExecutionTasks and executes them sequentially."""

    # CAPABILITY: agents.plan_executor.initialize
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

    # CAPABILITY: agent.plan.execute
    async def execute_plan(self, plan: List[ExecutionTask]):
        """Executes the entire plan, one task at a time."""
        for i, task in enumerate(plan, 1):
            log.info(f"--- Executing Step {i}/{len(plan)}: {task.step} ---")
            await self._execute_task_with_timeout(task)

    # CAPABILITY: agent.task.execute_with_timeout
    async def _execute_task_with_timeout(self, task: ExecutionTask):
        """Execute task with timeout protection."""
        timeout = self.config.task_timeout
        try:
            await asyncio.wait_for(self._execute_task(task), timeout=timeout)
        except asyncio.TimeoutError:
            raise PlanExecutionError(f"Task '{task.step}' timed out after {timeout}s")

    # CAPABILITY: agent.plan.execute_task
    async def _execute_task(self, task: ExecutionTask):
        """Dispatcher that executes a single task from a plan based on its action type."""
        action_map = {
            "add_capability_tag": self._execute_add_tag,
            "create_file": self._execute_create_file,
            "edit_function": self._execute_edit_function,
            "create_proposal": self._execute_create_proposal,
            "delete_file": self._execute_delete_file,  # Wire in the new action
        }
        if task.action in action_map:
            await action_map[task.action](task.params)
        else:
            log.warning(f"Skipping task: Unknown action '{task.action}'.")

    # --- THIS IS THE NEW METHOD ---
    # CAPABILITY: agent.plan_executor.delete_file
    async def _execute_delete_file(self, params: TaskParams):
        """Executes the 'delete_file' action."""
        file_path_str = params.file_path
        if not file_path_str:
            raise PlanExecutionError("Missing 'file_path' for delete_file action.")

        full_path = self.repo_path / file_path_str
        if not full_path.exists():
            log.warning(
                f"File '{file_path_str}' to be deleted does not exist. Skipping."
            )
            return

        # Perform the deletion
        full_path.unlink()
        log.info(f"🗑️  Deleted file: {file_path_str}")

        # If using git, commit the deletion
        if self.config.auto_commit and self.git_service.is_git_repo():
            # Use git rm for proper tracking of the deletion
            self.git_service._run_command(["git", "rm", file_path_str])
            self.git_service.commit(
                f"refactor(cleanup): Remove obsolete file {file_path_str}"
            )

    # CAPABILITY: agent.proposal.create
    async def _execute_create_proposal(self, params: TaskParams):
        """Executes the 'create_proposal' action."""
        target_path = params.file_path
        content = params.code
        justification = params.justification

        if not all([target_path, content, justification]):
            raise PlanExecutionError("Missing required parameters for create_proposal.")

        proposal_id = str(uuid.uuid4())[:8]
        proposal_filename = (
            f"cr-{proposal_id}-{target_path.split('/')[-1].replace('.py','')}.yaml"
        )
        proposal_path = self.repo_path / ".intent/proposals" / proposal_filename

        proposal_content = {
            "target_path": target_path,
            "action": "replace_file",
            "justification": justification,
            "content": content,
        }

        yaml_content = yaml.dump(
            proposal_content, indent=2, default_flow_style=False, sort_keys=True
        )

        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(yaml_content, encoding="utf-8")
        log.info(f"🏛️  Created constitutional proposal: {proposal_filename}")

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(str(proposal_path))
            self.git_service.commit(
                f"feat(proposal): Create proposal for {target_path}"
            )

    # CAPABILITY: agent.plan_executor.add_capability_tag
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

    # CAPABILITY: agent.plan_executor.create_file
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

    # CAPABILITY: agent.code_editor.edit
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
