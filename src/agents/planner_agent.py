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

from pydantic import ValidationError

from core.clients import OrchestratorClient, GeneratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from core.prompt_pipeline import PromptPipeline
from core.validation_pipeline import validate_code
from shared.utils.parsing import parse_write_blocks
from shared.logger import getLogger

# Local imports for agent-specific models and utils
from agents.models import ExecutionTask, ExecutionProgress, PlannerConfig, TaskParams, TaskStatus
from agents.utils import PlanExecutionContext, SymbolLocator

log = getLogger(__name__)

# Context for structured logging
execution_context = contextvars.ContextVar('execution_context')

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

    def _setup_logging_context(self, goal: str, plan_id: str):
        """Setup structured logging context for better observability."""
        execution_context.set({
            'goal': goal,
            'plan_id': plan_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """Extract JSON with multiple strategies and better error handling."""
        strategies = [
            lambda t: re.search(r'```json\s*(\[.*?\])\s*```', t, re.DOTALL),
            lambda t: re.search(r'(\[.*?\])', t, re.DOTALL),
            lambda t: re.search(r'(\{.*?\})', t, re.DOTALL)
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                match = strategy(text)
                if match:
                    json_str = match.group(1)
                    parsed = json.loads(json_str)
                    log.debug(f"JSON extracted using strategy {i+1}")
                    return parsed
            except (json.JSONDecodeError, AttributeError) as e:
                log.debug(f"Strategy {i+1} failed: {e}")
        log.error(f"Failed to extract JSON from response: {text[:200]}...")
        return None

    def _log_plan_summary(self, plan: List[ExecutionTask]) -> None:
        """Log a readable summary of the execution plan."""
        log.info(f"📋 Execution Plan Summary ({len(plan)} tasks):")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. [{task.action}] {task.step}")

    # CAPABILITY: llm_orchestration
    def create_execution_plan(self, high_level_goal: str) -> List[ExecutionTask]:
        """Creates a detailed, step-by-step execution plan from a high-level goal."""
        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self._setup_logging_context(high_level_goal, plan_id)
        
        log.info(f"🧠 Decomposing goal into an execution plan...")
        
        prompt_template = textwrap.dedent("""
            You are a hyper-competent, meticulous system architect AI for the CORE project. Your task is to decompose a high-level goal into a precise, machine-readable JSON execution plan.

            Your entire output MUST be a single, valid JSON array of objects.

            **System Context:**
            - All available capabilities are defined in: [[include:.intent/project_manifest.yaml]]
            - The full codebase structure is in: [[include:.intent/knowledge/knowledge_graph.json]]

            **High-Level Goal:**
            "{goal}"

            **Instructions & Rules:**
            1.  For goals requiring code modification, you MUST generate tasks with `action: "add_capability_tag"`.
            2.  Each task object MUST contain the keys: `step`, `action`, and `params`.
            3.  The `params` object for `add_capability_tag` MUST contain: `file_path`, `symbol_name`, `tag`.
            4.  Do NOT generate free-form prompts. Generate structured action objects.

            **Example of a PERFECT plan for adding a tag:**
            ```json
            [
              {{
                "step": "Tag the '_run_command' function in git_service.py",
                "action": "add_capability_tag",
                "params": {{
                  "file_path": "src/core/git_service.py",
                  "symbol_name": "_run_command",
                  "tag": "change_safety_enforcement"
                }}
              }}
            ]
            ```
            Generate the complete, syntactically correct JSON plan now.
        """).strip()

        final_prompt = prompt_template.format(goal=high_level_goal)
        enriched_prompt = self.prompt_pipeline.process(final_prompt)
        
        for attempt in range(self.config.max_retries):
            try:
                response_text = self.orchestrator.make_request(enriched_prompt, user_id="planner_agent")
                parsed_json = self._extract_json_from_response(response_text)
                if not parsed_json: raise ValueError("No valid JSON found in response")
                if isinstance(parsed_json, dict): parsed_json = [parsed_json]
                
                validated_plan = [ExecutionTask(**task) for task in parsed_json]
                self._log_plan_summary(validated_plan)
                return validated_plan
                
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    log.error("FATAL: Failed to create valid plan after max retries.")
        return []

    async def _find_symbol_line_async(self, file_path: str, symbol_name: str) -> Optional[int]:
        """Async version using thread pool for file I/O."""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            full_path = self.repo_path / file_path
            return await loop.run_in_executor(
                executor, self.symbol_locator.find_symbol_line, full_path, symbol_name
            )

    async def _execute_task_with_timeout(self, task: ExecutionTask, timeout: int = None) -> None:
        """Execute task with timeout protection."""
        timeout = timeout or self.config.task_timeout
        try:
            await asyncio.wait_for(self._execute_task(task), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Task '{task.step}' timed out after {timeout}s")

    async def execute_plan(self, plan: List[ExecutionTask], 
                          progress_callback: Optional[Callable[[ExecutionProgress], None]] = None) -> Tuple[bool, str]:
        """Executes a plan, running each task in sequence with progress tracking."""
        if not plan: return False, "Plan is empty or invalid."
        
        progress = ExecutionProgress(total_tasks=len(plan), completed_tasks=0)
        
        with PlanExecutionContext(self):
            for i, task in enumerate(plan):
                log.info(f"--- Step {i + 1}/{len(plan)}: {task.step} ---")
                try:
                    await self._execute_task_with_timeout(task, self.config.task_timeout)
                    progress.completed_tasks += 1
                except Exception as e:
                    error_detail = str(e)
                    log.error(f"Step failed with error: {error_detail}", exc_info=True)
                    return False, f"Plan failed at step {i + 1} ('{task.step}'): {error_detail}"
        
        return True, "✅ Plan executed successfully."

    # CAPABILITY: change_safety_enforcement
    async def _execute_add_tag(self, params: TaskParams, step_name: str):
        """Executes the surgical 'add_capability_tag' action."""
        file_path, symbol_name, tag = params.file_path, params.symbol_name, params.tag
        line_number = await self._find_symbol_line_async(file_path, symbol_name)
        if not line_number: raise RuntimeError(f"Could not find symbol '{symbol_name}' in '{file_path}'.")
        
        full_path = self.repo_path / file_path
        lines = full_path.read_text(encoding='utf-8').splitlines()
        
        insertion_index = line_number - 1
        if insertion_index > 0 and f"# CAPABILITY: {tag}" in lines[insertion_index - 1]:
            log.info(f"Tag '{tag}' already exists for '{symbol_name}'. Skipping.")
            return

        indentation = len(lines[insertion_index]) - len(lines[insertion_index].lstrip(' '))
        lines.insert(insertion_index, f"{' ' * indentation}# CAPABILITY: {tag}")
        modified_code = "\n".join(lines)

        validation_result = validate_code(file_path, modified_code)
        if validation_result["status"] != "clean":
            raise RuntimeError(f"Surgical modification failed validation: {validation_result['errors']}")
            
        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: {step_name}", suggested_path=file_path, code=validation_result["code"]
        )
        self.file_handler.confirm_write(pending_id)

        if self.config.auto_commit and self.git_service.is_git_repo():
            self.git_service.add(file_path)
            self.git_service.commit(f"refactor(capability): Add '{tag}' tag to {symbol_name}")

    async def _execute_task(self, task: ExecutionTask) -> None:
        """Dispatcher that executes a single task from a plan based on its action type."""
        if task.action == "add_capability_tag":
            await self._execute_add_tag(task.params, task.step)
        else:
            log.warning(f"Skipping task: Unknown action '{task.action}'.")