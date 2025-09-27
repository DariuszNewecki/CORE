# src/core/agents/plan_executor.py
"""
Executes a sequence of predefined code modification tasks including file creation,
function editing, capability tagging, and proposal generation.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import List

import yaml

from core.agents.code_editor import CodeEditor
from core.agents.utils import SymbolLocator
from core.file_handler import FileHandler
from core.git_service import GitService

# --- START OF AMENDMENT: Import the new async validator ---
from core.validation_pipeline import validate_code_async

# --- END OF AMENDMENT ---
from features.governance.audit_context import AuditorContext
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError, PlannerConfig, TaskParams

log = getLogger(__name__)


# ID: a2b23de4-07fa-4a66-8f29-783934079956
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
        self.file_context: dict[str, str] = {}  # To store content from read_file
        self.auditor_context = AuditorContext(self.repo_path)
        # --- START OF AMENDMENT: Pre-load the auditor's knowledge graph ---
        # This is a performance optimization and ensures the context is ready for async calls.
        asyncio.create_task(self.auditor_context.load_knowledge_graph())
        # --- END OF AMENDMENT ---

    # ID: 65f105d2-27e4-4fca-8f96-27decc90bca5
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
            "read_file": self._execute_read_file,
            "list_files": self._execute_list_files,
            "edit_file": self._execute_edit_file,
            "add_capability_tag": self._execute_add_tag,
            "create_file": self._execute_create_file,
            "edit_function": self._execute_edit_function,
            "create_proposal": self._execute_create_proposal,
            "delete_file": self._execute_delete_file,
        }
        if task.action in action_map:
            await action_map[task.action](task.params)
        else:
            log.warning(f"Skipping task: Unknown action '{task.action}'.")

    async def _execute_read_file(self, params: TaskParams):
        """Executes the 'read_file' action and stores content in context."""
        file_path_str = params.file_path
        if not file_path_str:
            raise PlanExecutionError("Missing 'file_path' for read_file action.")

        full_path = self.repo_path / file_path_str
        if not full_path.exists():
            raise PlanExecutionError(f"File to be read does not exist: {file_path_str}")

        if full_path.is_dir():
            raise PlanExecutionError(
                f"Cannot read '{file_path_str}' because it is a directory. Use 'list_files' instead."
            )

        self.file_context[file_path_str] = full_path.read_text(encoding="utf-8")
        log.info(f"📖 Read file '{file_path_str}' into context.")

    async def _execute_list_files(self, params: TaskParams):
        """Executes the 'list_files' action and stores the result in context."""
        dir_path_str = params.file_path
        if not dir_path_str:
            raise PlanExecutionError("Missing 'file_path' for list_files action.")

        full_path = self.repo_path / dir_path_str
        if not full_path.is_dir():
            raise PlanExecutionError(
                f"Directory to be listed does not exist or is not a directory: {dir_path_str}"
            )

        contents = []
        for item in full_path.iterdir():
            contents.append(item.name)

        self.file_context[dir_path_str] = "\n".join(sorted(contents))
        log.info(f"📁 Listed contents of '{dir_path_str}' into context.")

    async def _execute_edit_file(self, params: TaskParams):
        """Executes the 'edit_file' action using the context from 'read_file'."""
        file_path_str = params.file_path
        new_content = params.code
        if not all([file_path_str, new_content is not None]):
            raise PlanExecutionError(
                "Missing 'file_path' or 'code' for edit_file action."
            )

        full_path = self.repo_path / file_path_str
        if not full_path.exists():
            raise PlanExecutionError(
                f"File to be edited does not exist: {file_path_str}"
            )

        # --- START OF AMENDMENT: Use the async validator ---
        validation_result = await validate_code_async(
            file_path_str, new_content, auditor_context=self.auditor_context
        )
        # --- END OF AMENDMENT ---
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(
                f"Generated code for '{file_path_str}' failed validation.",
                violations=validation_result["violations"],
            )

        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: edit file {file_path_str}",
            suggested_path=file_path_str,
            code=validation_result["code"],
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path_str)
            self.git_service.commit(f"feat: Modify file {file_path_str}")

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

        full_path.unlink()
        log.info(f"🗑️  Deleted file: {file_path_str}")

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service._run_command(["git", "rm", file_path_str])
            self.git_service.commit(
                f"refactor(cleanup): Remove obsolete file {file_path_str}"
            )

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

        original_line = lines[insertion_index]
        indentation_spaces = len(original_line) - len(original_line.lstrip(" "))
        lines.insert(insertion_index, f"{' ' * indentation_spaces}# ID: {tag}")

        modified_code = "\n".join(lines)

        # --- START OF AMENDMENT: Use the async validator ---
        validation_result = await validate_code_async(
            file_path, modified_code, auditor_context=self.auditor_context
        )
        # --- END OF AMENDMENT ---
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
        if not all([file_path, code is not None]):
            raise PlanExecutionError(
                "Missing 'file_path' or 'code' for create_file action."
            )

        full_path = self.repo_path / file_path
        if full_path.exists():
            raise FileExistsError(
                f"File '{file_path}' already exists. Use 'edit_function' instead."
            )

        # --- START OF AMENDMENT: Use the async validator ---
        validation_result = await validate_code_async(
            file_path, code, auditor_context=self.auditor_context
        )
        # --- END OF AMENDMENT ---
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
        if not all([file_path, symbol_name, new_code is not None]):
            raise PlanExecutionError(
                "Missing required parameters for edit_function action."
            )

        full_path = self.repo_path / file_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"Cannot edit function, file not found: '{file_path}'"
            )

        original_code = await self._executor(None, full_path.read_text, "utf-8")

        # --- START OF AMENDMENT: Use the async validator ---
        validation_result = await validate_code_async(
            file_path, new_code, auditor_context=self.auditor_context
        )
        # --- END OF AMENDMENT ---
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
