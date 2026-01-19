# src/features/self_healing/test_generation/generation_workflow.py

"""
Coordinates initial test generation and validation.
"""

from __future__ import annotations

import time

from features.self_healing.complexity_filter import ComplexityFilter
from features.self_healing.test_context_analyzer import ModuleContext
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from .automatic_repair import AutomaticRepairService
from .code_extractor import CodeExtractor
from .context_builder import ContextPackageBuilder


logger = getLogger(__name__)


# ID: 25fe8cfd-a3f2-458c-b02f-e004dacbd1ba
class GenerationWorkflow:
    """Handles initial test generation and complexity filtering."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        complexity_filter: ComplexityFilter,
        auto_repair: AutomaticRepairService,
        max_complexity: str = "MODERATE",
    ):
        self.cognitive = cognitive_service
        self.context_builder = ContextPackageBuilder()
        self.code_extractor = CodeExtractor()
        self.complexity_filter = complexity_filter
        self.auto_repair = auto_repair

    # ID: da4981a0-403c-42d6-84e5-9478ca4fd980
    async def check_complexity(self, module_path: str) -> bool:
        """Check if module complexity is acceptable for test generation."""
        try:
            full_path = settings.REPO_PATH / module_path
            complexity_check = self.complexity_filter.should_attempt(full_path)
            if not complexity_check["should_attempt"]:
                logger.warning("Skipping %s due to complexity filter", module_path)
                return False
            return True
        except Exception as exc:
            logger.warning("Complexity check failed for %s: %s", module_path, exc)
            return False

    # ID: e246df81-5063-4518-b6ac-e13a716a8b48
    async def build_context(self, module_path: str) -> ModuleContext:
        """Build module context for test generation."""
        return await self.context_builder.build(module_path)

    # ID: d3a80664-59cc-4831-9651-cf59cca349e7
    async def generate_initial_code(
        self, module_context: ModuleContext, goal: str, target_coverage: float
    ) -> str | None:
        """
        Generate initial test code via LLM.

        Note: Prompt building is currently handled inline.
        TODO: Extract to PromptBuilder when implemented.
        """
        # Build prompt inline (PromptBuilder not yet implemented)
        prompt = self._build_prompt(module_context, goal, target_coverage)

        llm_client = await self.cognitive.aget_client_for_role("Coder")
        raw_response = await llm_client.make_request_async(prompt, user_id="test_gen")

        code = self.code_extractor.extract(raw_response)
        if not code:
            self._save_debug_artifact("failed_extract", raw_response or "")
            return None

        # Apply initial automatic repairs
        code, repairs = self.auto_repair.apply_all_repairs(code)
        if repairs:
            logger.info("Applied initial repairs: %s", ", ".join(repairs))

        return code

    def _build_prompt(
        self, module_context: ModuleContext, goal: str, target_coverage: float
    ) -> str:
        """
        Build test generation prompt inline.

        TODO: Move to dedicated PromptBuilder class when implemented.
        """
        return f"""Generate pytest tests for the following module.

Goal: {goal}
Target Coverage: {target_coverage}%

Module: {module_context.module_path}
Import Path: {module_context.import_path}

Generate comprehensive test cases."""

    def _save_debug_artifact(self, name: str, content: str) -> None:
        """Save failed generation artifacts for inspection."""
        try:
            debug_dir = settings.REPO_PATH / "work" / "testing" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            filename = f"{name}_{timestamp}.txt"
            (debug_dir / filename).write_text(content, encoding="utf-8")
            logger.info("Saved debug artifact: %s", debug_dir / filename)
        except Exception as e:
            logger.warning("Failed to save debug artifact: %s", e)
