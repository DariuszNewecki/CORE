# src/agents/planner_agent.py

import json
import re
import textwrap
import ast
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from core.clients import OrchestratorClient, GeneratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from core.prompt_pipeline import PromptPipeline
from core.self_correction_engine import attempt_correction
from core.validation_pipeline import validate_code
from shared.utils.parsing import parse_write_blocks

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
                 intent_guard: IntentGuard):
        """Initializes the PlannerAgent with all necessary service dependencies."""
        self.orchestrator = orchestrator_client
        self.generator = generator_client
        self.file_handler = file_handler
        self.git_service = git_service
        self.intent_guard = intent_guard
        self.repo_path = self.file_handler.repo_path
        self.prompt_pipeline = PromptPipeline(self.repo_path)

    def _extract_json_from_response(self, text: str) -> str:
        """Extracts a JSON object or array from a raw text response."""
        match = re.search(r"```json\n([\s\S]*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
        if match:
            return match.group(0).strip()
        return ""

    # CAPABILITY: llm_orchestration
    def create_execution_plan(self, high_level_goal: str) -> List[Dict]:
        """Creates a detailed, step-by-step execution plan from a high-level goal."""
        print(f"🧠 Planner: Creating execution plan for goal: '{high_level_goal}'")
        
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
        
        try:
            print("  -> Calling Orchestrator LLM to generate the plan... this may take a moment.")
            response_text = self.orchestrator.make_request(enriched_prompt, user_id="planner_agent")
            print("  -> Orchestrator responded. Parsing JSON plan...")
            json_string = self._extract_json_from_response(response_text)
            if not json_string:
                raise ValueError(f"Planner LLM did not return a valid JSON plan. Response: {response_text}")
            plan = json.loads(json_string)
            print(f"✅ Planner: LLM-based plan created successfully with {len(plan)} step(s).")
            return plan
        except (ValueError, json.JSONDecodeError) as e:
            print(f"❌ Planner: FATAL - Failed during LLM plan creation. Error: {e}")
            return []

    async def execute_plan(self, plan: List[Dict]) -> Tuple[bool, str]:
        """Executes a plan, running each task in sequence."""
        print("\n--- 🚀 Executing Plan ---")
        if not plan:
            return False, "Plan is empty or invalid."
        for i, task in enumerate(plan):
            step_name = task.get('step', 'Unnamed Step')
            print(f"\n--- Step {i + 1}/{len(plan)}: {step_name} ---")
            try:
                await self._execute_task(task)
            except Exception as e:
                error_detail = str(e)
                print(f"❌ Planner: Step failed with error: {error_detail}")
                if self.git_service.is_git_repo():
                    print("  -> Attempting to roll back last commit due to failure...")
                    self.git_service.rollback_last_commit()
                return False, f"Plan failed at step {i + 1} ('{step_name}'): {error_detail}"
        return True, "✅ Plan executed successfully."

    def _find_symbol_line(self, file_path: str, symbol_name: str) -> Optional[int]:
        """Finds the starting line number of a function or class in a file."""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return None
        code = full_path.read_text(encoding='utf-8')
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == symbol_name:
                        # Return the 1-based line number
                        return node.lineno
        except SyntaxError:
            return None
        return None

    # CAPABILITY: change_safety_enforcement
    async def _execute_add_tag(self, params: Dict, step_name: str):
        """Executes the surgical 'add_capability_tag' action."""
        file_path = params.get("file_path")
        symbol_name = params.get("symbol_name")
        tag = params.get("tag")

        if not all([file_path, symbol_name, tag]):
            raise ValueError("Missing required parameters for 'add_capability_tag' action.")

        print(f"  1. Finding insertion point for symbol '{symbol_name}' in '{file_path}'...")
        line_number = self._find_symbol_line(file_path, symbol_name)
        if not line_number:
            raise RuntimeError(f"Could not find symbol '{symbol_name}' in '{file_path}'.")
        
        # Adjust to 0-based index for list insertion
        insertion_index = line_number - 1

        print(f"  2. Reading file and preparing modification at line {line_number}...")
        full_path = self.repo_path / file_path
        lines = full_path.read_text(encoding='utf-8').splitlines()

        # Check if tag already exists
        if insertion_index > 0 and f"# CAPABILITY: {tag}" in lines[insertion_index - 1]:
            print(f"  ✅ Capability tag '{tag}' already exists for '{symbol_name}'. Skipping.")
            return

        # Determine indentation
        original_line = lines[insertion_index]
        indentation = len(original_line) - len(original_line.lstrip(' '))
        tag_line = f"{' ' * indentation}# CAPABILITY: {tag}"
        
        lines.insert(insertion_index, tag_line)
        modified_code = "\n".join(lines)

        print("  3. Validating surgically modified code...")
        validation_result = validate_code(file_path, modified_code)
        
        if validation_result["status"] != "clean":
            # This should be rare now, but the safety net is still crucial.
            raise RuntimeError(f"Surgical modification for {file_path} failed validation: {validation_result['errors']}")

        print("  4. Staging and confirming write...")
        final_code = validation_result["code"]
        pending_id = self.file_handler.add_pending_write(
            prompt=f"Goal: {step_name}",
            suggested_path=file_path,
            code=final_code
        )
        confirmation_result = self.file_handler.confirm_write(pending_id)
        if confirmation_result.get('status') != 'success':
            raise RuntimeError(f"Failed to confirm write for {file_path}: {confirmation_result.get('message')}")

        print(f"  ✅ Write confirmed for '{file_path}'")
        
        if self.git_service.is_git_repo():
            print("  5. Committing change to repository...")
            self.git_service.add(file_path)
            commit_message = f"refactor(capability): Add '{tag}' tag to {symbol_name}"
            self.git_service.commit(commit_message)

    async def _execute_task(self, task: Dict) -> None:
        """Dispatcher that executes a single task from a plan based on its action type."""
        action = task.get("action")
        params = task.get("params", {})
        step_name = task.get("step", "Unnamed Step")

        if action == "add_capability_tag":
            await self._execute_add_tag(params, step_name)
        # Placeholder for future generic tasks. We will remove this path once fully confident.
        # elif task.get("prompt"):
        #     await self._execute_generic_prompt_task(task)
        else:
            print(f"  -> Skipping task: Unknown or unsupported action '{action}'.")
            return