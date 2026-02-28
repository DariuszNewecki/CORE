# src/will/agents/code_generation/code_generator.py
# ID: 4a272fc9-4ce5-40ae-afa3-fd6eadceea73

"""
Code generation specialist responsible for prompt construction and LLM interaction.

CONSTITUTIONAL REFACTORING (Feb 2026):
- Modularized from 700+ LOC monolith.
- Main class delegates to focused modules.

- Removed direct settings import to comply with architecture.boundary.settings_access.
- Now utilizes injected PathResolver for all constitutional artifact location.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models.refusal_result import RefusalResult

from .extraction import extract_code_constitutionally, repair_basic_syntax
from .prompt_builders import (
    build_enriched_prompt,
    build_semantic_prompt,
    build_standard_prompt,
)


if TYPE_CHECKING:
    from shared.infrastructure.context.service import ContextService
    from shared.models import ExecutionTask
    from shared.path_resolver import PathResolver  # Added for type safety
    from will.orchestration.cognitive_service import CognitiveService
    from will.orchestration.decision_tracer import DecisionTracer
    from will.orchestration.prompt_pipeline import PromptPipeline
    from will.tools.architectural_context_builder import ArchitecturalContextBuilder

logger = getLogger(__name__)


def _resolve_prompt_template_path(
    path_resolver: PathResolver, prompt_name: str
) -> Path | None:
    """
    Resolve a prompt template path via the provided PathResolver.
    """
    try:
        path = path_resolver.prompt(prompt_name)
        if path.exists():
            return path
        return None
    except Exception as e:
        logger.warning("Failed to resolve prompt template '%s': %s", prompt_name, e)
        return None


# ID: ac97401b-a517-4bf2-ac0b-e86e57b799bb
class CodeGenerator:
    """Handles prompt construction and code generation via LLM."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        path_resolver: PathResolver,  # ADDED: Boundary alignment
        prompt_pipeline: PromptPipeline,
        tracer: DecisionTracer,
        context_builder: ArchitecturalContextBuilder | None = None,
        context_service: ContextService | None = None,
    ):
        """
        Initialize code generator.
        """
        self.cognitive_service = cognitive_service
        self.path_resolver = path_resolver
        self.prompt_pipeline = prompt_pipeline
        self.tracer = tracer
        self.context_builder = context_builder
        self.context_service = context_service
        self.semantic_enabled = context_builder is not None
        self.context_enrichment_enabled = context_service is not None

    # ID: 08c73be8-7d10-4399-b527-a7702fc9cecd
    async def generate_code(
        self,
        task: ExecutionTask,
        goal: str,
        context_str: str,
        pattern_id: str,
        pattern_requirements: str,
    ) -> str | RefusalResult:
        """
        Generate code for the given task.
        """
        logger.info("Generating code for task: '%s'...", task.step)

        target_file = task.params.file_path or "unknown.py"
        try:
            target_path = Path(target_file)
            if target_path.is_absolute():
                target_file = str(target_path.relative_to(self.path_resolver.repo_root))
        except Exception:
            pass
        symbol_name = task.params.symbol_name or ""

        # Priority 1: Semantic mode (full architectural context)
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

            prompt = build_semantic_prompt(
                arch_context=arch_context,
                task=task,
                manual_context=context_str,
                pattern_requirements=pattern_requirements,
            )

        # Priority 2: Context-enriched mode (ContextPackage)
        elif self.context_enrichment_enabled and self.context_service:
            logger.info("  -> Using Context-Enriched Mode (ContextPackage)")

            context_package = await self._build_context_package(
                task, goal, target_file, symbol_name
            )

            prompt = build_enriched_prompt(
                task=task,
                goal=goal,
                context_package=context_package,
                manual_context=context_str,
                pattern_requirements=pattern_requirements,
            )

        # Priority 3: Basic mode (string context only)
        else:
            logger.info("  -> Using Standard Template (Basic Context)")
            prompt = build_standard_prompt(
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

        # OBSERVABILITY FIX: Log raw LLM response for debugging
        logger.debug("Raw LLM response length: %d chars", len(raw_response))
        logger.debug("Raw LLM response preview: %s", raw_response[:200])

        # Record LLM response in decision trace
        self.tracer.record(
            agent="CodeGenerator",
            decision_type="llm_response_received",
            rationale=f"LLM returned {len(raw_response)} characters",
            chosen_action="Extracting code from response",
            context={
                "response_length": len(raw_response),
                "response_preview": raw_response[:500],
            },
            confidence=1.0,
        )

        # CONSTITUTIONAL EXTRACTION: Traced, explicit, refusal-first
        code_or_refusal = extract_code_constitutionally(
            raw_response, task.step, self.tracer
        )

        if isinstance(code_or_refusal, RefusalResult):
            return code_or_refusal

        return repair_basic_syntax(code_or_refusal)

    async def _build_context_package(
        self,
        task: ExecutionTask,
        goal: str,
        target_file: str,
        symbol_name: str,
    ) -> dict[str, Any]:
        """
        Build rich context package for code generation.
        """
        try:
            task_spec = {
                "task_id": f"codegen_{symbol_name}_{hash(goal) & 0xFFFFFFFF:08x}",
                "task_type": "code_generation",
                "target_file": target_file,
                "target_symbol": symbol_name,
                "summary": f"{goal} - {task.step}",
                "scope": {
                    "traversal_depth": 2,  # Get related symbols
                    "include": [target_file] if target_file != "unknown.py" else [],
                },
                "constraints": {
                    "max_tokens": 30000,  # Reasonable context size
                    "max_items": 20,  # Focus on most relevant items
                },
            }

            context_package = await self.context_service.build_for_task(
                task_spec, use_cache=True
            )

            items_count = len(context_package.get("context", []))
            logger.debug("  -> Built ContextPackage with %d items", items_count)

            return context_package

        except Exception as e:
            logger.warning("ContextPackage build failed, using minimal context: %s", e)
            return {"context": [], "provenance": {}}
