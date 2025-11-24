# src/will/agents/coder_agent.py

"""
Provides the CoderAgent, a specialist AI agent responsible for all code
generation, validation, and self-correction tasks within the CORE system.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from shared.config import get_path_or_none, settings
from shared.logger import getLogger
from shared.models import ExecutionTask
from shared.utils.parsing import extract_python_code_from_response
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.self_correction_engine import attempt_correction
from will.orchestration.validation_pipeline import validate_code_async

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: f60524bd-7e84-429c-88b7-4d226487d894
class CoderAgent:
    """A specialist agent for writing, validating, and fixing code."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        auditor_context: AuditorContext,
    ):
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context

        agent_policy = settings.load("charter.policies.agent.agent_policy")
        agent_behavior = agent_policy.get("execution_agent", {})
        self.max_correction_attempts = agent_behavior.get("max_correction_attempts", 2)

    def _build_reuse_guidance_block(self, task: ExecutionTask) -> str:
        """
        Build a small, explicit reuse instruction block injected into the prompt.

        This does NOT call ContextPackage or any heavy analysis; it simply
        nudges the LLM to:
        - Prefer existing helpers in shared.universal / shared.utils
        - Avoid re-inventing generic utilities inside feature modules
        - Respect the code_standards.style.universal_helper_first rule
        """
        file_path = task.params.file_path
        symbol_name = task.params.symbol_name or ""

        return f"""
[CORE REUSE GUARDRAILS]

Before you introduce any new helper functions, classes, or utilities for this task:

1. Prefer reuse over reinvention:
   - FIRST, assume there may already be a reusable helper under:
     - shared.universal
     - shared.utils
   - If you need something like:
     * path / file operations
     * parallel execution
     * hashing / embeddings
     * header / metadata parsing
     * generic AST / symbol utilities
     then:
     - Reuse or extend existing helpers in these modules instead of
       creating yet another local copy.

2. Only create new helpers when truly domain-specific:
   - If the logic is tightly bound to this feature or file and would not
     make sense anywhere else, it MAY live next to {file_path}.
   - If the logic is generic or cross-cutting, propose that it belongs in
     shared.utils or shared.universal instead of in this file.

3. Respect code_standards.style.universal_helper_first:
   - Do NOT introduce near-duplicate helpers that mirror existing ones in
     shared.universal or shared.utils.
   - When in doubt, prefer:
       from shared.universal import ...
       from shared.utils.<module> import ...
     over creating a new local helper.

4. Keep the public surface small:
   - Only export symbols that are truly part of the capability surface.
   - Keep orchestration / glue helpers private (prefixed with '_').

Current file target:
- File: {file_path}
- Symbol (if any): {symbol_name}

Follow these guardrails while generating code.
"""

    # ID: 1bb9b0c2-12e7-497c-b39b-716a7df06bdf
    async def generate_and_validate_code_for_task(
        self,
        task: ExecutionTask,
        high_level_goal: str,
        context_str: str,
    ) -> str:
        """
        The main entry point for the CoderAgent. It orchestrates the
        generate-validate-correct loop and returns clean, validated code.

        Raises:
            Exception: If valid code cannot be produced after all attempts.
        """
        current_code = await self._generate_code_for_task(
            task,
            high_level_goal,
            context_str,
        )

        for attempt in range(self.max_correction_attempts + 1):
            logger.info("  -> Validation attempt %s...", attempt + 1)
            validation_result = await validate_code_async(
                task.params.file_path,
                current_code,
                auditor_context=self.auditor_context,
            )

            if validation_result["status"] == "clean":
                logger.info("  -> ✅ Code is constitutionally valid.")
                return validation_result["code"]

            if attempt >= self.max_correction_attempts:
                raise Exception(
                    f"Self-correction failed after "
                    f"{self.max_correction_attempts + 1} attempts."
                )

            logger.warning("  -> ⚠️ Code failed validation. Attempting self-correction.")
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
                raise Exception("Self-correction failed to produce a valid fix.")

        raise Exception("Could not produce valid code after all attempts.")

    async def _generate_code_for_task(
        self,
        task: ExecutionTask,
        goal: str,
        context_str: str,
    ) -> str:
        """
        Builds the prompt and calls the LLM to generate the initial code.

        Uses a robust extractor to:
        - Pull only the Python code block from the LLM response
        - Strip markdown fences / chatter
        - Perform light auto-repair on formatting noise
        """
        logger.info("✍️  Generating code for task: '%s'...", task.step)

        template_path = get_path_or_none("mind.prompts.standard_task_generator")
        prompt_template = (
            template_path.read_text(encoding="utf-8")
            if template_path and template_path.exists()
            else "Implement step '{step}' for goal '{goal}' targeting {file_path}."
        )

        base_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=task.params.file_path,
            symbol_name=task.params.symbol_name or "",
        )

        reuse_block = self._build_reuse_guidance_block(task)
        final_prompt = f"{base_prompt}\n\n{reuse_block}"

        # Let PromptPipeline inject [[context:...]] etc.
        enriched_prompt = self.prompt_pipeline.process(final_prompt + context_str)

        generator = await self.cognitive_service.aget_client_for_role("Coder")
        raw_response = await generator.make_request_async(
            enriched_prompt,
            user_id="coder_agent",
        )

        code = extract_python_code_from_response(raw_response)
        if code is None:
            # Try a more permissive, auto-repair fallback
            code = self._fallback_extract_python(raw_response)

        if code is None:
            preview = (raw_response or "")[:400]
            logger.error(
                "CoderAgent: No valid Python code found in LLM response. Preview: %s",
                preview,
            )
            raise ValueError("CoderAgent: No valid Python code block in LLM response.")

        # Final light syntax repair for common LLM glitches (e.g. mismatched quotes)
        code = self._repair_basic_syntax(code)

        return code

    def _repair_basic_syntax(self, code: str) -> str:
        """
        Attempt to repair simple LLM-induced syntax issues, such as
        mismatched quotes in single-line string expressions.

        Strategy:
        - If the full code parses, return as-is.
        - On SyntaxError, normalize lines that contain both single and
          double quotes with odd counts by unifying to double quotes.
        - If the repaired version still does not parse, fall back to the
          original code so that validation can report the failure.
        """
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            # Only attempt repair if the whole block is broken
            pass

        lines = code.splitlines()
        fixed_lines: list[str] = []

        for line in lines:
            if '"' in line and "'" in line:
                dq = line.count('"')
                sq = line.count("'")
                # If either quote count is odd, unify to double quotes
                if dq % 2 != 0 or sq % 2 != 0:
                    fixed_lines.append(line.replace("'", '"'))
                    continue

            fixed_lines.append(line)

        fixed_code = "\n".join(fixed_lines)

        try:
            ast.parse(fixed_code)
            return fixed_code
        except SyntaxError:
            # If still broken, return original so the validator surfaces it
            return code

    def _normalize_escaped_newlines(self, code: str) -> str:
        """
        Fix LLM outputs that embed literal '\\n' in code.

        Converts sequences like:
            "\\n"  → actual newline
        Also removes stray backslashes at start-of-line, which
        cause Black to choke:
            "\\def test()" → "def test()"
        """
        # Replace escaped newlines with real newlines
        code = code.replace("\\n", "\n")

        fixed_lines = []
        for line in code.splitlines():
            # remove leading stray backslashes
            if line.startswith("\\"):
                fixed_lines.append(line.lstrip("\\"))
            else:
                fixed_lines.append(line)
        return "\n".join(fixed_lines)

    def _fallback_extract_python(self, text: str) -> str | None:
        """
        Auto-repair extractor for messy LLM responses.

        Strategy:
        - Strip fenced code markers like ```python / ```
        - Drop leading non-code chatter until first obvious code line
        - Return remaining lines as a best-effort code block
        """
        if not text:
            return None

        # Remove obvious fenced code markers
        cleaned = text.replace("```python", "").replace("```py", "").replace("```", "")

        lines = [ln.rstrip() for ln in cleaned.splitlines()]

        # Find first "code-ish" line
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
