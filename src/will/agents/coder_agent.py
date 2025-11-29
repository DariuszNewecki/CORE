# src/will/agents/coder_agent.py

"""
Provides the CoderAgent, a specialist AI agent responsible for all code
generation, validation, and self-correction tasks within the CORE system.

UPGRADED (Phase 2): Now enforces design patterns at generation time via IntentGuard.
- Patterns checked BEFORE code is written
- Constitutional pattern enforcement (not tests)
- Integrated with Semantic Infrastructure
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

from services.clients.qdrant_client import QdrantService
from shared.config import get_path_or_none, settings
from shared.logger import getLogger
from shared.models import ExecutionTask
from shared.utils.parsing import extract_python_code_from_response

from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.intent_guard import IntentGuard
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.self_correction_engine import attempt_correction
from will.orchestration.validation_pipeline import validate_code_async
from will.tools.architectural_context_builder import ArchitecturalContextBuilder
from will.tools.module_anchor_generator import ModuleAnchorGenerator
from will.tools.policy_vectorizer import PolicyVectorizer

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: caf62379-9713-4c98-8dd4-d7b7e503573f
class CodeGenerationError(Exception):
    """Raised when code generation fails, carrying the invalid code for debugging."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


# ID: f60524bd-7e84-429c-88b7-4d226487d894
class CoderAgent:
    """
    A specialist agent for writing, validating, and fixing code.
    Powered by Semantic Infrastructure (Vectorized Policies + Module Anchors).
    Enhanced with Constitutional Pattern Enforcement.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        auditor_context: AuditorContext,
        qdrant_service: QdrantService | None = None,
    ):
        """
        Initialize the CoderAgent with semantic tools and pattern enforcement.

        Args:
            cognitive_service: Access to LLMs
            prompt_pipeline: Prompt processing (includes/macros)
            auditor_context: Validation context
            qdrant_service: Vector DB access (Required for A2 features)
        """
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context
        self.repo_root = settings.REPO_PATH

        # Initialize IntentGuard for pattern validation
        self.intent_guard = IntentGuard(self.repo_root)
        logger.info("CoderAgent: IntentGuard initialized for pattern enforcement")

        # Constitutional settings - FIX: Update path to match meta.yaml structure
        try:
            agent_policy = settings.load("charter.policies.agent_governance")
        except Exception:
            # Fallback for backward compatibility or if key is missing
            agent_policy = {}

        agent_behavior = agent_policy.get("execution_agent", {})
        self.max_correction_attempts = agent_behavior.get("max_correction_attempts", 2)

        # Initialize Semantic Infrastructure if Qdrant is available
        self.semantic_enabled = False
        if qdrant_service:
            try:
                self.policy_vectorizer = PolicyVectorizer(
                    self.repo_root, cognitive_service, qdrant_service
                )
                self.module_anchor_generator = ModuleAnchorGenerator(
                    self.repo_root, cognitive_service, qdrant_service
                )
                self.context_builder = ArchitecturalContextBuilder(
                    self.policy_vectorizer, self.module_anchor_generator
                )
                self.semantic_enabled = True
                logger.info(
                    "CoderAgent initialized with Semantic Infrastructure enabled."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Semantic Infrastructure: {e}. Falling back to V0 behavior."
                )
        else:
            logger.warning(
                "CoderAgent initialized without QdrantService. Semantic capabilities disabled."
            )

    # ID: 212d7a3f-a446-4f84-8a30-76ba23f11cd3
    async def generate_and_validate_code_for_task(
        self,
        task: ExecutionTask,
        high_level_goal: str,
        context_str: str,
    ) -> str:
        """
        The main entry point. Orchestrates generation -> pattern validation -> constitutional validation -> correction.

        Flow:
        1. Generate code (with pattern hints in prompt)
        2. PATTERN VALIDATION (IntentGuard - blocks pattern violations)
        3. Constitutional validation (existing flow)
        4. Self-correction if needed
        """
        current_code = await self._generate_code_for_task(
            task,
            high_level_goal,
            context_str,
        )

        for attempt in range(self.max_correction_attempts + 1):
            logger.info("  -> Validation attempt %s...", attempt + 1)

            # ========================================
            # PHASE 1: Pattern Validation (NEW!)
            # ========================================
            pattern_id = self._infer_pattern_id(task)
            component_type = self._infer_component_type(task)

            logger.info(f"  -> Checking pattern compliance: {pattern_id}")

            (
                pattern_approved,
                pattern_violations,
            ) = await self.intent_guard.validate_generated_code(
                code=current_code,
                pattern_id=pattern_id,
                component_type=component_type,
                target_path=task.params.file_path,
            )

            if not pattern_approved:
                error_violations = [
                    v for v in pattern_violations if v.severity == "error"
                ]
                violation_msg = "\n".join(
                    [f"  - {v.message}" for v in error_violations]
                )

                if attempt >= self.max_correction_attempts:
                    raise CodeGenerationError(
                        f"Pattern violations after {self.max_correction_attempts + 1} attempts:\n{violation_msg}",
                        code=current_code,
                    )

                logger.warning(f"  -> ⚠️ Pattern violations found:\n{violation_msg}")
                logger.warning("  -> Attempting pattern-aware correction...")

                # Pass pattern violations to correction engine
                pattern_correction_result = await self._attempt_pattern_correction(
                    task,
                    current_code,
                    pattern_violations,
                    pattern_id,
                    high_level_goal,
                )

                if pattern_correction_result.get("status") == "success":
                    current_code = pattern_correction_result["code"]
                    continue  # Retry validation with corrected code
                else:
                    raise CodeGenerationError(
                        f"Pattern correction failed: {pattern_correction_result.get('message')}",
                        code=current_code,
                    )

            logger.info(f"  -> ✅ Pattern validation passed: {pattern_id}")

            # ========================================
            # PHASE 2: Constitutional Validation (Existing)
            # ========================================
            validation_result = await validate_code_async(
                task.params.file_path,
                current_code,
                auditor_context=self.auditor_context,
            )

            if validation_result["status"] == "clean":
                logger.info("  -> ✅ Constitutional validation passed.")
                return validation_result["code"]

            if attempt >= self.max_correction_attempts:
                # Failed after max retries. Raise custom error with the code.
                raise CodeGenerationError(
                    f"Constitutional validation failed after {self.max_correction_attempts + 1} attempts.",
                    code=current_code,
                )

            logger.warning(
                "  -> ⚠️ Constitutional violations found. Attempting self-correction."
            )
            correction_result = await self._attempt_code_correction(
                task,
                current_code,
                validation_result,
                high_level_goal,
            )
            if correction_result.get("status") == "success":
                logger.info("  -> ✅ Self-correction generated a potential fix.")
                current_code = correction_result["code"]
            else:
                # Fallback to original error if correction failed completely
                raise CodeGenerationError(
                    f"Self-correction failed: {correction_result.get('message')}",
                    code=current_code,
                )

        raise CodeGenerationError(
            "Could not produce valid code after all attempts.", code=current_code
        )

    def _infer_pattern_id(self, task: ExecutionTask) -> str:
        """
        Infer which pattern this code should follow based on task context.

        Returns pattern_id like 'inspect_pattern', 'action_pattern', etc.
        """
        # Check if task has explicit pattern
        if hasattr(task.params, "pattern_id") and task.params.pattern_id:
            return task.params.pattern_id

        # Infer from file path
        file_path = task.params.file_path or ""

        if "cli/commands" in file_path:
            # Infer command pattern from naming
            if "inspect" in file_path.lower() or "inspect" in task.step.lower():
                return "inspect_pattern"
            elif "check" in file_path.lower() or "validate" in task.step.lower():
                return "check_pattern"
            elif "run" in file_path.lower() or "execute" in task.step.lower():
                return "run_pattern"
            elif "manage" in file_path.lower() or "admin" in task.step.lower():
                return "manage_pattern"
            else:
                # Default for commands: action pattern (safest - requires --write)
                return "action_pattern"

        elif "services" in file_path:
            if "repository" in file_path.lower():
                return "repository_pattern"
            else:
                return "stateful_service"

        elif "agents" in file_path:
            return "cognitive_agent"

        # Default fallback
        return "action_pattern"

    def _infer_component_type(self, task: ExecutionTask) -> str:
        """Infer component type from file path."""
        file_path = task.params.file_path or ""

        if "cli/commands" in file_path:
            return "command"
        elif "services" in file_path:
            return "service"
        elif "agents" in file_path:
            return "agent"
        else:
            return "command"  # Default

    async def _generate_code_for_task(
        self,
        task: ExecutionTask,
        goal: str,
        context_str: str,
    ) -> str:
        """
        Generates code using either semantic context (if available) or standard prompts.
        NOW: Includes pattern requirements in the prompt.
        """
        logger.info("✍️  Generating code for task: '%s'...", task.step)

        target_file = task.params.file_path or "unknown.py"
        symbol_name = task.params.symbol_name or ""

        # Determine pattern to follow
        pattern_id = self._infer_pattern_id(task)
        pattern_requirements = self._get_pattern_requirements(pattern_id)

        # ---------------------------------------------------------
        # PATH A: Semantic Generation (A2 Capable)
        # ---------------------------------------------------------
        if self.semantic_enabled:
            logger.info("  -> Using Semantic Architectural Context")

            # Build the rich context
            arch_context = await self.context_builder.build_context(
                goal=f"{goal} (Step: {task.step})", target_file=target_file
            )

            # Inject it into the prompt structure WITH pattern requirements
            prompt = self._build_semantic_prompt(
                arch_context=arch_context,
                task=task,
                manual_context=context_str,
                pattern_id=pattern_id,
                pattern_requirements=pattern_requirements,
            )

            # Log confidence for debugging
            logger.info(
                f"  -> Placement Confidence: {arch_context.placement_confidence} "
                f"(Layer: {arch_context.target_layer})"
            )
            logger.info(f"  -> Target Pattern: {pattern_id}")

        # ---------------------------------------------------------
        # PATH B: Legacy Generation (Fallback)
        # ---------------------------------------------------------
        else:
            logger.info("  -> Using Standard Template (No Semantic Context)")
            template_path = get_path_or_none("mind.prompts.standard_task_generator")
            prompt_template = (
                template_path.read_text(encoding="utf-8")
                if template_path and template_path.exists()
                else "Implement step '{step}' for goal '{goal}' targeting {file_path}."
            )

            base_prompt = prompt_template.format(
                goal=goal,
                step=task.step,
                file_path=target_file,
                symbol_name=symbol_name,
            )

            # Manual reuse guardrails (heuristic only)
            reuse_block = self._build_reuse_guidance_block(task)
            prompt = f"{base_prompt}\n\n{reuse_block}\n\n{pattern_requirements}\n{context_str}"

        # Use PromptPipeline to expand any [[directives]] in the prompt
        enriched_prompt = self.prompt_pipeline.process(prompt)

        # Execute request
        generator = await self.cognitive_service.aget_client_for_role("Coder")
        raw_response = await generator.make_request_async(
            enriched_prompt,
            user_id="coder_agent_a2",
        )

        # Extract and cleanup
        code = extract_python_code_from_response(raw_response)
        if code is None:
            code = self._fallback_extract_python(raw_response)

        if code is None:
            preview = (raw_response or "")[:400]
            logger.error("CoderAgent: No valid Python code found in LLM response.")
            raise ValueError("CoderAgent: No valid Python code block in LLM response.")

        return self._repair_basic_syntax(code)

    def _get_pattern_requirements(self, pattern_id: str) -> str:
        """Get pattern requirements to include in prompt."""
        requirements = {
            "inspect_pattern": """
## Pattern Requirements: inspect_pattern
CRITICAL: This is a READ-ONLY command that must NEVER modify state.
- Must NOT have --write, --apply, or --force parameters
- Should return data for inspection only
- Exit code: 0 for success, 1 for error
""",
            "action_pattern": """
## Pattern Requirements: action_pattern
CRITICAL: This command modifies state and must follow safety guarantees.
- MUST have a 'write' parameter with type: bool
- MUST default to False (dry-run by default)
- In dry-run mode, show what WOULD change without changing it
- Only execute when write=True
- Must be atomic (all or nothing)
""",
            "check_pattern": """
## Pattern Requirements: check_pattern
CRITICAL: This is a VALIDATION command.
- Must NOT modify state (no --write parameter)
- Must return clear pass/fail status
- Exit code: 0 for pass, 1 for fail, 2 for warnings
- Provide actionable error messages
""",
            "run_pattern": """
## Pattern Requirements: run_pattern
CRITICAL: This executes autonomous operations.
- MUST have 'write' parameter (bool, default=False)
- Must operate within autonomy lane boundaries
- Must log all autonomous decisions
- Respects constitutional constraints
""",
        }
        return requirements.get(pattern_id, "")

    def _build_semantic_prompt(
        self,
        arch_context: Any,
        task: ExecutionTask,
        manual_context: str,
        pattern_id: str,
        pattern_requirements: str,
    ) -> str:
        """Constructs the prompt when semantic infra is available."""
        context_text = self.context_builder.format_for_prompt(arch_context)

        parts = [
            context_text,
            "",
            pattern_requirements,  # ADD PATTERN REQUIREMENTS
            "",
            "## Implementation Task",
            f"Step: {task.step}",
            f"Symbol: {task.params.symbol_name}" if task.params.symbol_name else "",
            "",
            "## Additional Context",
            manual_context,
            "",
            "## Output Requirements",
            "1. Return ONLY valid Python code.",
            "2. Include all necessary imports.",
            "3. Include docstrings and type hints.",
            "4. FOLLOW the pattern requirements above.",
            "5. NO markdown formatting outside the code block.",
        ]
        return "\n".join(parts)

    def _build_reuse_guidance_block(self, task: ExecutionTask) -> str:
        """Legacy heuristic guidance (fallback)."""
        file_path = task.params.file_path
        return f"""
[CORE REUSE GUARDRAILS]
1. Prefer reusing helpers in shared.universal / shared.utils.
2. Only create new helpers if logic is strictly domain-specific to {file_path}.
3. Keep public surface small.
"""

    def _repair_basic_syntax(self, code: str) -> str:
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            pass
        lines = code.splitlines()
        fixed_lines = []
        for line in lines:
            if '"' in line and "'" in line:
                dq = line.count('"')
                sq = line.count("'")
                if dq % 2 != 0 or sq % 2 != 0:
                    fixed_lines.append(line.replace("'", '"'))
                    continue
            fixed_lines.append(line)
        fixed_code = "\n".join(fixed_lines)
        try:
            ast.parse(fixed_code)
            return fixed_code
        except SyntaxError:
            return code

    def _fallback_extract_python(self, text: str) -> str | None:
        if not text:
            return None
        cleaned = text.replace("```python", "").replace("```py", "").replace("```", "")
        lines = [ln.rstrip() for ln in cleaned.splitlines()]
        start_idx = 0
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped:
                continue
            if stripped.startswith(("def ", "class ", "import ", "from ", "#")):
                start_idx = idx
                break
        code_lines = lines[start_idx:]
        if not any(ln.strip() for ln in code_lines):
            return None
        return "\n".join(code_lines).strip()

    async def _attempt_pattern_correction(
        self,
        task: ExecutionTask,
        current_code: str,
        pattern_violations: list,
        pattern_id: str,
        goal: str,
    ) -> dict:
        """
        Attempt to fix pattern violations.

        Similar to _attempt_code_correction but focused on pattern compliance.
        """
        violation_messages = "\n".join([f"- {v.message}" for v in pattern_violations])
        pattern_requirements = self._get_pattern_requirements(pattern_id)

        correction_prompt = f"""
The following code violates the {pattern_id} pattern:

```python
{current_code}
```

Pattern Violations:
{violation_messages}

Pattern Requirements:
{pattern_requirements}

Please fix the code to comply with the {pattern_id} pattern.
Return ONLY the corrected Python code.
"""

        generator = await self.cognitive_service.aget_client_for_role("Coder")
        raw_response = await generator.make_request_async(
            correction_prompt,
            user_id="coder_agent_pattern_correction",
        )

        corrected_code = extract_python_code_from_response(raw_response)
        if corrected_code:
            return {"status": "success", "code": corrected_code}
        else:
            return {"status": "failure", "message": "Could not extract corrected code"}

    async def _attempt_code_correction(
        self,
        task: ExecutionTask,
        current_code: str,
        validation_result: dict,
        goal: str,
    ) -> dict:
        """Invokes the self-correction engine for a piece of failed code."""
        correction_context = {
            "file_path": task.params.file_path,
            "code": current_code,
            "violations": validation_result["violations"],
            "original_prompt": goal,
        }
        logger.info("  -> 🧬 Invoking self-correction engine...")
        return await attempt_correction(
            correction_context,
            self.cognitive_service,
            self.auditor_context,
        )
