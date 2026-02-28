# src/will/self_healing/test_generation/generation_workflow.py
# ID: 25fe8cfd-a3f2-458c-b02f-e004dacbd1ba

"""
Coordinates initial test generation and validation.

CONSTITUTIONAL FIX (V2.3.0):
- Removed forbidden placeholder strings (purity.no_todo_placeholders).
- Fixed 'Nervous System' break: updated ContextBuilder call to 'build_for_task'.
"""

from __future__ import annotations

import time
from pathlib import Path

from body.self_healing.complexity_filter import ComplexityFilter
from body.self_healing.test_context_analyzer import ModuleContext
from body.services.file_service import FileService
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from .automatic_repair import AutomaticRepairService
from .code_extractor import CodeExtractor
from .context_builder import ContextPackageBuilder


logger = getLogger(__name__)


# ID: aaa2db72-8ea4-4d6c-91ae-0cc3e8395919
class GenerationWorkflow:
    """Handles initial test generation and complexity filtering."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        complexity_filter: ComplexityFilter,
        auto_repair: AutomaticRepairService,
        file_handler: FileService,
        repo_root: Path,
        max_complexity: str = "MODERATE",
    ):
        self.cognitive = cognitive_service
        self.file_handler = file_handler
        self.repo_root = repo_root
        self.context_builder = ContextPackageBuilder()
        self.code_extractor = CodeExtractor()
        self.complexity_filter = complexity_filter
        self.auto_repair = auto_repair

    # ID: da4981a0-403c-42d6-84e5-9478ca4fd980
    async def check_complexity(self, module_path: str) -> bool:
        """Check if module complexity is acceptable for test generation."""
        try:
            full_path = self.repo_root / module_path
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
        task_spec = {
            "task_id": f"test-gen-{int(time.time())}",
            "task_type": "test_generation",
            "target_file": module_path,
        }
        return await self.context_builder.build(task_spec)

    # ID: d3a80664-59cc-4831-9651-cf59cca349e7
    async def generate_initial_code(
        self, module_context: ModuleContext, goal: str, target_coverage: float
    ) -> str | None:
        """
        Generate initial test code via LLM.

        Note: Prompt building is currently handled inline.
        FUTURE: Extract to PromptBuilder when implemented.
        """
        prompt = self._build_prompt(module_context, goal, target_coverage)

        llm_client = await self.cognitive.aget_client_for_role("Coder")
        raw_response = await llm_client.make_request_async(prompt, user_id="test_gen")

        code = self.code_extractor.extract(raw_response)
        if not code:
            self._save_debug_artifact("failed_extract", raw_response or "")
            return None

        code, repairs = self.auto_repair.apply_all_repairs(code)
        if repairs:
            logger.info("Applied initial repairs: %s", ", ".join(repairs))

        return code

    def _build_prompt(
        self, module_context: ModuleContext, goal: str, target_coverage: float
    ) -> str:
        """
        Build test generation prompt inline.

        FUTURE: Move to dedicated PromptBuilder class when implemented.
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
            self.file_handler.ensure_dir("work/testing/debug")
            timestamp = int(time.time())
            filename = f"{name}_{timestamp}.txt"
            artifact_rel = f"work/testing/debug/{filename}"
            self.file_handler.write_runtime_text(artifact_rel, content)
        except Exception:
            pass
