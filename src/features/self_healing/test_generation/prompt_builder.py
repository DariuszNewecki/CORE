# src/features/self_healing/test_generation/prompt_builder.py
"""
PromptBuilder – creates enriched test-generation prompts.
"""

from __future__ import annotations

from shared.config import settings
from will.orchestration.prompt_pipeline import PromptPipeline


# ID: 82b2ae1a-663e-441a-bb30-e066a6340aad
class PromptBuilder:
    """Builds final enriched prompt for test generation."""

    def __init__(self):
        self.pipeline = PromptPipeline(repo_path=settings.REPO_PATH)
        self.template = self._load_template()

    def _load_template(self) -> str:
        path = settings.get_path("mind.prompts.test_generator")
        if not path or not path.exists():
            raise FileNotFoundError("Test generator prompt missing")
        return path.read_text(encoding="utf-8")

    # ID: bcdd542b-5589-4eb3-a1bf-cc3c1046e8a7
    def build(self, context, goal: str, target_coverage: float) -> str:
        """Compose enriched prompt with full context."""
        base = self.template.format(
            module_path=context.module_path,
            import_path=context.import_path,
            target_coverage=target_coverage,
            module_code=context.source_code,
            goal=goal,
            safe_module_name=context.module_name,
        )

        enriched = (
            "# CRITICAL CONTEXT\n\n"
            f"{context.to_prompt_context()}\n\n"
            "---\n\n"
            f"{base}\n\n"
            "---\n\n"
            "# PRIORITY FOCUS\n"
            "Uncovered functions:\n"
            f"{chr(10).join(f'- {f}' for f in context.uncovered_functions[:10])}\n\n"
            "RULES:\n"
            "• Use pytest (sync tests only)\n"
            "• Mock all external deps\n"
            "• NEVER use async/await in tests\n"
            '• ALWAYS use triple quotes (r"""...""") for strings containing code snippets\n'
            "• WRAP YOUR FINAL CODE in <final_code>...</final_code> tags. This is CRITICAL.\n"
        )

        return self.pipeline.process(enriched)
