# src/agents/planner_agent.py
"""
The primary agent responsible for decomposing high-level goals into executable plans.
"""
import json
import re
import textwrap
import asyncio
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
import contextvars
from pydantic import ValidationError

from core.clients import OrchestratorClient, GeneratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from core.prompt_pipeline import PromptPipeline
from shared.logger import getLogger

from agents.models import ExecutionTask, PlannerConfig
from agents.utils import PlanExecutionContext
from agents.plan_executor import PlanExecutor, PlanExecutionError

log = getLogger(__name__)
execution_context = contextvars.ContextVar('execution_context')

# CAPABILITY: code_generation
class PlannerAgent:
    """
    Decomposes goals into plans, generates code for each step, and then
    delegates execution to the PlanExecutor.
    """
    
    def __init__(self,
                 orchestrator_client: OrchestratorClient,
                 generator_client: GeneratorClient,
                 file_handler: FileHandler,
                 git_service: GitService,
                 intent_guard: IntentGuard, # <<< THIS IS THE FIX
                 config: Optional[PlannerConfig] = None):
        """Initializes the PlannerAgent with service dependencies."""
        self.orchestrator = orchestrator_client
        self.generator = generator_client
        self.file_handler = file_handler
        self.git_service = git_service
        self.intent_guard = intent_guard # <<< THIS IS THE FIX
        self.config = config or PlannerConfig()
        self.prompt_pipeline = PromptPipeline(self.file_handler.repo_path)
        self.executor = PlanExecutor(self.file_handler, self.git_service, self.config)

    def _setup_logging_context(self, goal: str, plan_id: str):
        """Setup structured logging context for better observability."""
        execution_context.set({
            'goal': goal, 'plan_id': plan_id, 'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """Extracts a JSON object or array from a raw text response."""
        match = re.search(r'```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                log.warning("Found a JSON markdown block, but it contained invalid JSON.")
        
        try:
            start_index = text.find('{')
            if start_index == -1: start_index = text.find('[')
            if start_index == -1: return None
            
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(text[start_index:])
            return obj
        except (json.JSONDecodeError, ValueError):
            log.warning("Could not find a valid JSON object using boundary detection.")

        log.error(f"Failed to extract any valid JSON from the LLM response.")
        return None

    def _log_plan_summary(self, plan: List[ExecutionTask]) -> None:
        """Log a readable summary of the execution plan."""
        log.info(f"📋 Execution Plan Summary ({len(plan)} tasks):")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. [{task.action}] {task.step}")
    
    def _validate_task_params(self, task: ExecutionTask):
        """Validates that a task has all the logically required parameters for its action."""
        params = task.params
        required = []
        if task.action == "add_capability_tag": required = ["file_path", "symbol_name", "tag"]
        elif task.action == "create_file": required = ["file_path"]
        elif task.action == "edit_function": required = ["file_path", "symbol_name"]
        
        if not all(getattr(params, p, None) for p in required):
            raise PlanExecutionError(f"Task '{task.step}' is missing required parameters for '{task.action}'.")

    # CAPABILITY: llm_orchestration
    def create_execution_plan(self, high_level_goal: str) -> List[ExecutionTask]:
        """Creates a high-level, code-agnostic execution plan."""
        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self._setup_logging_context(high_level_goal, plan_id)
        
        log.info(f"🧠 Step 1: Decomposing goal into a high-level plan...")
        
        prompt_template = textwrap.dedent("""
            You are a hyper-competent, meticulous system architect AI. Your task is to decompose a high-level goal into a JSON execution plan.
            Your entire output MUST be a single, valid JSON array of objects.

            **High-Level Goal:** "{goal}"

            **Available Actions & Required Parameters:**
            - Action: `create_file` -> Params: `{{ "file_path": "<path>" }}`
            - Action: `edit_function` -> Params: `{{ "file_path": "<path>", "symbol_name": "<func_name>" }}`
            - Action: `add_capability_tag` -> Params: `{{ "file_path": "<path>", "symbol_name": "<func_name>", "tag": "<tag_name>" }}`
            
            **CRITICAL RULE:** Do NOT include a `"code"` parameter in this step. Generate the code-free JSON plan now.
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
                for task in validated_plan: self._validate_task_params(task)
                
                self._log_plan_summary(validated_plan)
                return validated_plan
                
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise PlanExecutionError("Failed to create a valid high-level plan after max retries.")
        return []

    async def _generate_code_for_task(self, task: ExecutionTask, goal: str) -> str:
        """Generates the code content for a single task."""
        log.info(f"✍️ Step 2: Generating code for task: '{task.step}'...")
        if task.action not in ["create_file", "edit_function"]:
            return ""

        prompt_template = textwrap.dedent("""
            You are an expert Python programmer. Generate a single block of Python code to fulfill the task.
            **Overall Goal:** {goal}
            **Current Task:** {step}
            **Target File:** {file_path}
            **Target Symbol (if editing):** {symbol_name}
            **Instructions:** Your output MUST be ONLY the raw Python code. Do not wrap it in markdown blocks.
        """).strip()

        final_prompt = prompt_template.format(
            goal=goal, step=task.step, file_path=task.params.file_path,
            symbol_name=task.params.symbol_name or ""
        )
        enriched_prompt = self.prompt_pipeline.process(final_prompt)
        return self.generator.make_request(enriched_prompt, user_id="planner_agent_coder")

    async def execute_plan(self, high_level_goal: str) -> Tuple[bool, str]:
        """Creates a plan, generates code for it, and orchestrates its execution."""
        try:
            plan = self.create_execution_plan(high_level_goal)
        except PlanExecutionError as e:
            return False, str(e)
        if not plan: return False, "Plan is empty or invalid."
        
        log.info("--- Starting Code Generation Phase ---")
        for task in plan:
            task.params.code = await self._generate_code_for_task(task, high_level_goal)
            if task.action in ["create_file", "edit_function"] and not task.params.code:
                return False, f"Code generation failed for step: '{task.step}'"

        log.info("--- Handing off to Executor ---")
        with PlanExecutionContext(self):
            try:
                await self.executor.execute_plan(plan)
                return True, "✅ Plan executed successfully."
            except Exception as e:
                error_detail = str(e)
                log.error(f"Execution failed with error: {error_detail}", exc_info=True)
                if hasattr(e, 'violations') and e.violations:
                    log.error("Violations found:")
                    for v in e.violations:
                        log.error(f"  - [{v.get('rule')}] L{v.get('line')}: {v.get('message')}")
                return False, f"Plan execution failed: {error_detail}"