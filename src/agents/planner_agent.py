# src/agents/planner_agent.py
"""
The primary agent responsible for decomposing high-level goals into executable plans.
"""

import json
import re
import textwrap
import asyncio
from typing import List, Dict, Tuple, Optional, Callable
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import contextvars
import atexit

from pydantic import ValidationError

from core.clients import OrchestratorClient, GeneratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from core.prompt_pipeline import PromptPipeline
from core.validation_pipeline import validate_code
from shared.utils.parsing import parse_write_blocks
from shared.logger import getLogger

from agents.models import ExecutionTask, ExecutionProgress, PlannerConfig, TaskParams, TaskStatus
from agents.utils import PlanExecutionContext, SymbolLocator, CodeEditor

log = getLogger(__name__)

# Context for structured logging
execution_context = contextvars.ContextVar('execution_context')

class PlanExecutionError(Exception):
    """Custom exception for failures during plan creation or execution."""
    def __init__(self, message, violations=None):
        super().__init__(message)
        self.violations = violations or []

# CAPABILITY: code_generation
class PlannerAgent:
    """
    The primary agent responsible for decomposing high-level goals into executable plans.
    It orchestrates the generation, validation, and commitment of code changes.
    """
    
    def __init__(self,
                 orchestrator_client: OrchestratorClient,
                 generator_client: GeneratorClient,
                 file_handler: FileHandler,
                 git_service: GitService,
                 intent_guard: IntentGuard,
                 config: Optional[PlannerConfig] = None):
        """Initializes the PlannerAgent with all necessary service dependencies."""
        self.orchestrator = orchestrator_client
        self.generator = generator_client
        self.file_handler = file_handler
        self.git_service = git_service
        self.intent_guard = intent_guard
        self.config = config or PlannerConfig()
        self.repo_path = self.file_handler.repo_path
        self.prompt_pipeline = PromptPipeline(self.repo_path)
        self.symbol_locator = SymbolLocator()
        self.code_editor = CodeEditor()
        
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="planner_agent")
        atexit.register(self._cleanup_resources)

    def _cleanup_resources(self):
        """Clean up resources on shutdown."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=True)

    def __del__(self):
        """Ensure resources are cleaned up when the agent is garbage collected."""
        self._cleanup_resources()

    def _setup_logging_context(self, goal: str, plan_id: str):
        """Setup structured logging context for better observability."""
        execution_context.set({
            'goal': goal,
            'plan_id': plan_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    # --- THIS IS THE NEW, MORE ROBUST FUNCTION ---
    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """
        Extract JSON with multiple strategies and better error handling.
        """
        # Strategy 1: Look for a markdown code block with 'json'
        match = re.search(r'```json\s*(\{.*\}|\[.*\])\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                log.warning("Found a JSON markdown block, but it contained invalid JSON.")

        # Strategy 2: Look for any JSON-like string (starts with { or [)
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                log.warning("Found a JSON-like string, but it was invalid.")

        log.error(f"Failed to extract any valid JSON from the LLM response.")
        return None
    # --- END OF NEW FUNCTION ---

    def _log_plan_summary(self, plan: List[ExecutionTask]) -> None:
        """Log a readable summary of the execution plan."""
        log.info(f"📋 Execution Plan Summary ({len(plan)} tasks):")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. [{task.action}] {task.step}")
    
    def _validate_task_params(self, task: ExecutionTask):
        """Validates that a task has all the logically required parameters for its action."""
        params = task.params
        if task.action == "add_capability_tag":
            if not all([params.file_path, params.symbol_name, params.tag]):
                raise PlanExecutionError(f"Task '{task.step}' is missing required parameters for 'add_capability_tag'.")
        elif task.action == "create_file":
            if not params.file_path:
                raise PlanExecutionError(f"Task '{task.step}' is missing required parameter 'file_path' for 'create_file'.")
        elif task.action == "edit_function":
             if not all([params.file_path, params.symbol_name]):
                raise PlanExecutionError(f"Task '{task.step}' is missing required parameters for 'edit_function'.")

    # CAPABILITY: llm_orchestration
    def create_execution_plan(self, high_level_goal: str) -> List[ExecutionTask]:
        """Creates a high-level, code-agnostic execution plan."""
        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self._setup_logging_context(high_level_goal, plan_id)
        
        log.info(f"🧠 Step 1: Decomposing goal into a high-level plan...")
        
        prompt_template = textwrap.dedent("""
            You are a hyper-competent, meticulous system architect AI. Your task is to decompose a high-level goal into a JSON execution plan.
            Your entire output MUST be a single, valid JSON array of objects.

            **High-Level Goal:**
            "{goal}"

            **Reasoning Framework:**
            1.  Analyze the Goal: What is the user's core intent?
            2.  Choose the Right Tool: Select the correct action from the list below.
                - To CREATE a NEW file, use the `create_file` action.
                - To MODIFY an EXISTING file/function, use `edit_function`.
                - To ADD a #CAPABILITY tag to an EXISTING function, use `add_capability_tag`.
            3.  Construct the Plan: Build a JSON object for each step. **DO NOT generate any code content.** Just define the actions and targets.

            **Available Actions & Required Parameters (for this step):**
            - Action: `create_file` -> Params: `{{ "file_path": "<path_to_new_file>" }}`
            - Action: `edit_function` -> Params: `{{ "file_path": "<path_to_existing_file>", "symbol_name": "<function_to_edit>" }}`
            - Action: `add_capability_tag` -> Params: `{{ "file_path": "<path_to_existing_file>", "symbol_name": "<function_to_tag>", "tag": "<tag_name>" }}`
            
            **CRITICAL RULE:**
            - Every task object MUST include a `"step"` and `"action"` key.
            - The `"params"` object should ONLY contain the parameters listed above. DO NOT include a `"code"` parameter.

            Generate the complete, code-free JSON plan now.
        """).strip()

        final_prompt = prompt_template.format(goal=high_level_goal)
        enriched_prompt = self.prompt_pipeline.process(final_prompt)
        
        for attempt in range(self.config.max_retries):
            try:
                response_text = self.orchestrator.make_request(enriched_prompt, user_id="planner_agent_architect")
                parsed_json = self._extract_json_from_response(response_text)
                if not parsed_json: raise ValueError("No valid JSON found in response")
                if isinstance(parsed_json, dict): parsed_json = [parsed_json]
                
                validated_plan = [ExecutionTask(**task) for task in parsed_json]
                self._log_plan_summary(validated_plan)
                return validated_plan
                
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                log.warning(f"High-level plan creation attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    log.error("FATAL: Failed to create valid high-level plan after max retries.")
                    raise PlanExecutionError("Failed to create a valid high-level plan.")
        return []

    async def _generate_code_for_task(self, task: ExecutionTask, goal: str) -> str:
        """Generates the code content for a single task."""
        log.info(f"✍️ Step 2: Generating code for task: '{task.step}'...")

        if task.action not in ["create_file", "edit_function"]:
            return ""

        prompt_template = textwrap.dedent("""
            You are an expert Python programmer. Your task is to generate a single block of Python code to fulfill a specific step in a larger plan.

            **Overall Goal:** {goal}
            **Current Task:** {step}
            **Target File:** {file_path}

            **Instructions:**
            - Your output MUST be ONLY the raw Python code.
            - Do not wrap the code in markdown blocks (```python ... ```).
            - Do not add any conversational text or explanations.
            - Ensure the code is complete, correct, and ready to be written to a file.
            - If editing a function, you MUST provide the complete, new version of that function, including its decorator, signature, and docstring.
            
            Generate the code now.
        """).strip()

        final_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=task.params.file_path,
        )
        enriched_prompt = self.prompt_pipeline.process(final_prompt)
        
        return self.generator.make_request(enriched_prompt, user_id="planner_agent_coder")

    async def _find_symbol_line_async(self, file_path: str, symbol_name: str) -> Optional[int]:
        """Async version using shared thread pool for file I/O."""
        loop = asyncio.get_event_loop()
        full_path = self.repo_path / file_path
        return await loop.run_in_executor(
            self._executor, self.symbol_locator.find_symbol_line, full_path, symbol_name
        )

    async def _execute_task_with_timeout(self, task: ExecutionTask, timeout: int = None) -> None:
        """Execute task with timeout protection."""
        timeout = timeout or self.config.task_timeout
        try:
            await asyncio.wait_for(self._execute_task(task), timeout=timeout)
        except asyncio.TimeoutError:
            raise PlanExecutionError(f"Task '{task.step}' timed out after {timeout}s")

    async def execute_plan(self, high_level_goal: str) -> Tuple[bool, str]:
        """Creates and executes a plan in a two-step (Plan -> Generate -> Execute) process."""
        try:
            plan = self.create_execution_plan(high_level_goal)
        except PlanExecutionError as e:
            return False, str(e)

        if not plan: return False, "Plan is empty or invalid."
        
        progress = ExecutionProgress(total_tasks=len(plan), completed_tasks=0)
        
        with PlanExecutionContext(self):
            for i, task in enumerate(plan):
                log.info(f"--- Executing Step {i + 1}/{len(plan)}: {task.step} ---")
                try:
                    if task.action in ["create_file", "edit_function"]:
                        generated_code = await self._generate_code_for_task(task, high_level_goal)
                        if not generated_code:
                            raise PlanExecutionError("Code generation failed for this step.")
                        task.params.code = generated_code

                    await self._execute_task_with_timeout(task)
                    progress.completed_tasks += 1
                except Exception as e:
                    error_detail = str(e)
                    log.error(f"Step failed with error: {error_detail}", exc_info=True)
                    if hasattr(e, 'violations') and e.violations:
                        log.error("Violations found:")
                        for v in e.violations:
                            log.error(f"  - [{v.get('rule')}] L{v.get('line')}: {v.get('message')}")
                    return False, f"Plan failed at step {i + 1} ('{task.step}'): {error_detail}"
        
        return True, "✅ Plan executed successfully."

    async def _execute_add_tag(self, params: TaskParams):
        """Executes the surgical 'add_capability_tag' action."""
        file_path, symbol_name, tag = params.file_path, params.symbol_name, params.tag
        line_number = await self._find_symbol_line_async(file_path, symbol_name)
        if not line_number: raise PlanExecutionError(f"Could not find symbol '{symbol_name}' in '{file_path}'.")
        
        full_path = self.repo_path / file_path
        if not full_path.exists():
            raise PlanExecutionError(f"File '{file_path}' does not exist.")
            
        lines = full_path.read_text(encoding='utf-8').splitlines()
        
        insertion_index = line_number - 1
        if insertion_index > 0 and f"# CAPABILITY: {tag}" in lines[insertion_index - 1]:
            log.info(f"Tag '{tag}' already exists for '{symbol_name}'. Skipping.")
            return

        indentation = len(lines[insertion_index]) - len(lines[insertion_index].lstrip(' '))
        lines.insert(insertion_index, f"{' ' * indentation}# CAPABILITY: {tag}")
        modified_code = "\n".join(lines)

        validation_result = validate_code(file_path, modified_code)
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(f"Surgical modification for '{file_path}' failed validation.", violations=validation_result["violations"])
            
        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: add tag to {symbol_name}", suggested_path=file_path, code=validation_result["code"]
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(f"refactor(capability): Add '{tag}' tag to {symbol_name}")

    async def _execute_create_file(self, params: TaskParams):
        """Executes the 'create_file' action."""
        file_path, code = params.file_path, params.code
        full_path = self.repo_path / file_path
        if full_path.exists():
            raise FileExistsError(f"File '{file_path}' already exists. Use 'edit_function' or another edit action instead.")

        validation_result = validate_code(file_path, code)
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(f"Generated code for new file '{file_path}' failed validation.", violations=validation_result["violations"])

        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: create file {file_path}", suggested_path=file_path, code=validation_result["code"]
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(f"feat: Create new file {file_path}")
            
    async def _execute_edit_function(self, params: TaskParams):
        """Executes the 'edit_function' action using the CodeEditor."""
        file_path, symbol_name, new_code = params.file_path, params.symbol_name, params.code
        full_path = self.repo_path / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"Cannot edit function, file not found: '{file_path}'")

        loop = asyncio.get_event_loop()
        original_code = await loop.run_in_executor(self._executor, full_path.read_text, "utf-8")

        function_only = textwrap.dedent(new_code).strip()
        validation_result = validate_code(file_path, function_only)
        if validation_result["status"] == "dirty":
            raise PlanExecutionError(f"Modified code for '{file_path}' failed validation.", violations=validation_result["violations"])

        try:
            final_code = self.code_editor.replace_symbol_in_code(original_code, symbol_name, validation_result["code"])
        except ValueError as e:
            raise PlanExecutionError(f"Failed to edit code in '{file_path}': {e}")

        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: edit function {symbol_name} in {file_path}", suggested_path=file_path, code=final_code
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(f"feat: Modify function {symbol_name} in {file_path}")

    async def _execute_task(self, task: ExecutionTask) -> None:
        """Dispatcher that executes a single task from a plan based on its action type."""
        self._validate_task_params(task)

        if task.action == "add_capability_tag":
            await self._execute_add_tag(task.params)
        elif task.action == "create_file":
            await self._execute_create_file(task.params)
        elif task.action == "edit_function":
            await self._execute_edit_function(task.params)
        else:
            log.warning(f"Skipping task: Unknown action '{task.action}'.")
