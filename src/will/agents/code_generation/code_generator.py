# src/will/agents/code_generation/code_generator.py
"""
Code generation specialist responsible for prompt construction and LLM interaction.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response


if TYPE_CHECKING:
    from shared.models import ExecutionTask
    from will.orchestration.cognitive_service import CognitiveService
    from will.orchestration.decision_tracer import DecisionTracer
    from will.orchestration.prompt_pipeline import PromptPipeline
    from will.tools.architectural_context_builder import ArchitecturalContextBuilder

logger = getLogger(__name__)


def _resolve_prompt_template_path(logical_path: str) -> Path | None:
    """
    Resolve a prompt template path via settings meta.yaml mapping.

    This is intentionally local (not a shared shim):
    - Keeps caller logic explicit.
    - Avoids reintroducing legacy helper APIs into shared.config.
    """
    try:
        return settings.get_path(logical_path)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(
            "Failed to resolve prompt template path '%s': %s", logical_path, e
        )
        return None


# ID: 4a272fc9-4ce5-40ae-afa3-fd6eadceea73
class CodeGenerator:
    """Handles prompt construction and code generation via LLM."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        tracer: DecisionTracer,
        context_builder: ArchitecturalContextBuilder | None = None,
    ):
        """
        Initialize code generator.

        Args:
            cognitive_service: LLM orchestration service
            prompt_pipeline: Prompt enhancement pipeline
            tracer: Decision tracing system
            context_builder: Semantic context builder (optional)
        """
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.tracer = tracer
        self.context_builder = context_builder
        self.semantic_enabled = context_builder is not None

    # ID: 08c73be8-7d10-4399-b527-a7702fc9cecd
    async def generate_code(
        self,
        task: ExecutionTask,
        goal: str,
        context_str: str,
        pattern_id: str,
        pattern_requirements: str,
    ) -> str:
        """
        Generate code for the given task.

        Args:
            task: Execution task with parameters
            goal: High-level goal description
            context_str: Manual context string
            pattern_id: The pattern to follow
            pattern_requirements: Pattern requirements text

        Returns:
            Generated Python code as string
        """
        logger.info("✍️  Generating code for task: '%s'...", task.step)

        target_file = task.params.file_path or "unknown.py"
        symbol_name = task.params.symbol_name or ""

        if self.semantic_enabled and self.context_builder:
            logger.info("  -> Using Semantic Architectural Context")
            arch_context = await self.context_builder.build_context(
                goal=f"{goal} (Step: {task.step})", target_file=target_file
            )

            # DECISION TRACING: Record architectural decision
            if hasattr(arch_context, "chosen_module"):
                self.tracer.record(
                    agent="CodeGenerator",
                    decision_type="module_placement",
                    rationale=f"Semantic match for {target_file}",
                    chosen_action=f"Using module: {arch_context.chosen_module}",
                    alternatives=getattr(arch_context, "alternative_modules", []),
                    context={"symbol": symbol_name, "goal": goal},
                    confidence=getattr(arch_context, "confidence", 0.8),
                )

            prompt = self._build_semantic_prompt(
                arch_context=arch_context,
                task=task,
                manual_context=context_str,
                pattern_requirements=pattern_requirements,
            )
        else:
            logger.info("  -> Using Standard Template (No Semantic Context)")
            prompt = self._build_standard_prompt(
                task=task,
                goal=goal,
                context_str=context_str,
                pattern_requirements=pattern_requirements,
            )

        enriched_prompt = self.prompt_pipeline.process(prompt)
        generator = await self.cognitive_service.aget_client_for_role("Coder")

        # DECISION TRACING: Record LLM invocation
        self.tracer.record(
            agent="CodeGenerator",
            decision_type="llm_generation",
            rationale=f"Generating code for task: {task.step}",
            chosen_action=f"Using {generator.__class__.__name__} for code generation",
            alternatives=["Template-based generation", "Retrieve from examples"],
            context={"pattern_id": pattern_id, "target_file": target_file},
            confidence=0.9,
        )

        raw_response = await generator.make_request_async(
            enriched_prompt,
            user_id="coder_agent_a2",
        )

        code = extract_python_code_from_response(raw_response)
        if code is None:
            code = self._fallback_extract_python(raw_response)

        if code is None:
            raise ValueError(
                "CodeGenerator: No valid Python code block in LLM response."
            )

        return self._repair_basic_syntax(code)

    def _build_semantic_prompt(
        self,
        arch_context: Any,
        task: ExecutionTask,
        manual_context: str,
        pattern_requirements: str,
    ) -> str:
        """Build prompt using semantic architectural context."""
        context_text = self.context_builder.format_for_prompt(arch_context)
        parts = [
            context_text,
            "",
            pattern_requirements,
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

    def _build_standard_prompt(
        self,
        task: ExecutionTask,
        goal: str,
        context_str: str,
        pattern_requirements: str,
    ) -> str:
        """Build prompt using standard template."""
        target_file = task.params.file_path or "unknown.py"
        symbol_name = task.params.symbol_name or ""

        template_path = _resolve_prompt_template_path(
            "mind.prompts.standard_task_generator"
        )
        if template_path and template_path.exists():
            try:
                prompt_template = template_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(
                    "Failed to read prompt template '%s': %s", template_path, e
                )
                prompt_template = (
                    "Implement step '{step}' for goal '{goal}' targeting {file_path}."
                )
        else:
            prompt_template = (
                "Implement step '{step}' for goal '{goal}' targeting {file_path}."
            )

        base_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=target_file,
            symbol_name=symbol_name,
        )
        reuse_block = self._build_reuse_guidance_block(task)
        return (
            f"{base_prompt}\n\n{reuse_block}\n\n{pattern_requirements}\n{context_str}"
        )

    def _build_reuse_guidance_block(self, task: ExecutionTask) -> str:
        """Generate reuse guidance for the prompt."""
        file_path = task.params.file_path
        return f"""
[CORE REUSE GUARDRAILS]
1. Prefer reusing helpers in shared.universal / shared.utils.
2. Only create new helpers if logic is strictly domain-specific to {file_path}.
3. Keep public surface small.
"""

    def _repair_basic_syntax(self, code: str) -> str:
        """Attempt basic syntax repairs on generated code."""
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
        """Fallback code extraction when regex fails."""
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
