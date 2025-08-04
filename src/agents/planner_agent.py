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
from core.validation_pipeline import validate_code  # <-- ADD THIS IMPORT
from shared.utils.parsing import parse_write_blocks

# CAPABILITY: llm_orchestration
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

    def _extract_target_path_from_prompt(self, prompt: str) -> Optional[str]:
        """Parses a prompt to find the first [[write:path/to/file]] directive."""
        match = re.search(r'\[\[write:(.+?)\]\]', prompt)
        return match.group(1).strip() if match else None

    def _extract_json_from_response(self, text: str) -> str:
        """Extracts a JSON object or array from a raw text response."""
        match = re.search(r"```json\n([\s\S]*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
        if match:
            return match.group(0).strip()
        return ""

    # CAPABILITY: prompt_interpretation
    def create_execution_plan(self, high_level_goal: str) -> List[Dict]:
        """Creates a detailed, step-by-step execution plan from a high-level goal."""
        print(f"🧠 Planner: Creating execution plan for goal: '{high_level_goal}'")
        
        prompt = textwrap.dedent(f"""
            You are a hyper-competent, meticulous system architect AI for the CORE project. Your task is to decompose a high-level goal into a precise, machine-readable JSON execution plan.
            Your entire output MUST be a single, valid JSON array of objects.
            Each object in the plan MUST have these keys:
            - "step": A human-readable description of the task.
            - "prompt": A detailed, self-contained prompt for a Generator LLM, including all necessary context and a [[write:path/to/file]] block.
            - "expects_writes": A boolean indicating if the step should result in a file write.
            **High-Level Goal:** "{high_level_goal}"
            Generate the complete, self-contained, and syntactically correct JSON plan now.
        """).strip()

        try:
            response_text = self.orchestrator.make_request(prompt, user_id="planner_agent")
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

    # CAPABILITY: change_safety_enforcement
    def _govern_and_amend_code(self, code: str) -> str:
        """
        Validates and amends newly generated code to comply with constitutional
        standards before being written to disk. This is the core of the
        "immune system".

        Args:
            code (str): The raw Python code generated by the LLM.

        Returns:
            str: The amended code, compliant with governance.
        
        Raises:
            RuntimeError: If a critical governance check fails (e.g., missing docstring).
        """
        print("    3a. Governing and amending raw code...")
        try:
            tree = ast.parse(code)
            lines = code.splitlines()
            insertions = []

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # --- NEW DOCSTRING ENFORCEMENT ---
                    if not ast.get_docstring(node):
                        raise RuntimeError(f"Governance check failed: Symbol '{node.name}' is missing a required docstring.")
                    # ------------------------------------

                    # Check if a capability comment already exists on the line above
                    line_above_index = node.lineno - 2
                    if line_above_index < 0 or not lines[line_above_index].strip().startswith("# CAPABILITY:"):
                        # Prepare to insert the placeholder capability tag
                        indentation = ' ' * node.col_offset
                        insertions.append((node.lineno - 1, f"{indentation}# CAPABILITY: unassigned"))
            
            # Apply insertions in reverse order to not mess up line numbers
            for line_num, text in sorted(insertions, reverse=True):
                lines.insert(line_num, text)

            amended_code = "\n".join(lines)
            print("    3b. ✅ Code passed governance checks and was amended.")
            return amended_code
        except SyntaxError as e:
            print(f"    ⚠️  Could not parse generated code to govern it. Returning raw code. Error: {e}")
            return code # Return raw code if it can't be parsed

    # CAPABILITY: code_generation
    async def _execute_task(self, task: Dict) -> None:
        """Executes a single task from a plan, including code generation and file writing."""
        prompt = task.get("prompt")
        if not prompt:
            print("  -> Skipping task: No prompt provided.")
            return

        print("  1. Enriching prompt with directives...")
        enriched_prompt = self.prompt_pipeline.process(prompt)

        print("  2. Calling generation service...")
        generated_text = self.generator.make_request(enriched_prompt, user_id="planner_agent")
        write_blocks = parse_write_blocks(generated_text)
        
        if not write_blocks and task.get("expects_writes", True):
            print("  ⚠️  Generator failed to produce a valid write block. Initiating self-correction.")
            target_path = self._extract_target_path_from_prompt(enriched_prompt)
            if not target_path:
                raise RuntimeError("Cannot attempt self-correction: Could not determine target file path from prompt.")
            failure_context = {
                "file_path": target_path, "code": generated_text, "error_type": "missing_write_block",
                "details": "The Generator LLM produced code but failed to wrap it in [[write:...]] block.",
                "original_prompt": enriched_prompt,
            }
            correction_result = attempt_correction(failure_context)
            if correction_result.get("status") == "retry_staged":
                print("  ✅ Self-correction successful. Staged corrected code.")
                write_blocks = {correction_result["file_path"]: "Code from self-correction"} # This is a placeholder
            else:
                raise RuntimeError(f"Self-correction failed: {correction_result.get('message')}")
        
        written_files = []
        for file_path, code in write_blocks.items():
            print(f"  3. Governing code for '{file_path}'")
            governed_code = self._govern_and_amend_code(code)

            # --- NEW VALIDATION & SELF-CORRECTION STEP ---
            print(f"  4. Validating governed code for '{file_path}'...")
            validation_result = validate_code(file_path, governed_code)
            
            pending_id = None
            if validation_result["status"] == "clean":
                print("  ✅ Validation clean. Staging write.")
                final_code = validation_result["code"]
                pending_id = self.file_handler.add_pending_write(
                    prompt=enriched_prompt,
                    suggested_path=file_path,
                    code=final_code
                )
            else: # Validation is dirty, attempt self-correction
                print("  ⚠️  Validation failed. Initiating self-correction.")
                failure_context = {
                    "file_path": file_path,
                    "code": governed_code,
                    "error_type": "validation_failed",
                    "details": validation_result.get("errors", []),
                    "original_prompt": enriched_prompt,
                }
                correction_result = attempt_correction(failure_context)

                if correction_result.get("status") == "retry_staged":
                    print("  ✅ Self-correction successful. Using corrected & staged code.")
                    pending_id = correction_result["pending_id"]
                else:
                    raise RuntimeError(f"Self-correction failed after validation error: {correction_result.get('message')}")

            if not pending_id:
                raise RuntimeError(f"Logic error: No pending write ID was created for {file_path}")

            print(f"  5. Confirming write for '{file_path}' (ID: {pending_id})")
            confirmation_result = self.file_handler.confirm_write(pending_id)
            
            if confirmation_result.get('status') != 'success':
                raise RuntimeError(f"Failed to confirm write for {file_path}: {confirmation_result.get('message')}")
            
            print(f"  ✅ Write confirmed for '{file_path}'")
            written_files.append(file_path)

        if self.git_service.is_git_repo() and written_files:
            print("  6. Committing changes to repository...")
            for file_path in written_files:
                self.git_service.add(file_path)
            commit_message = f"feat(agent): {task.get('step', 'Automated code generation')}"
            self.git_service.commit(commit_message)