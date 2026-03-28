# src/will/self_healing/test_generation/llm_correction.py
"""
LLM-based code correction when automatic repairs are insufficient.

This is the "last resort" - only called when deterministic fixes don't work.
HEALED: attempt_correction uses PromptModel.invoke() — ai.prompt.model_required compliant.
"""

from __future__ import annotations

import json
from typing import Any

from body.self_healing.test_context_analyzer import ModuleContext
from mind.governance.audit_context import AuditorContext
from shared.ai.prompt_model import PromptModel
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parsing import parse_write_blocks
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.validation_pipeline import validate_code_async

from .code_extractor import CodeExtractor


logger = getLogger(__name__)


# ID: 16cae4db-0a04-44a2-b154-eb5162cba662
class LLMCorrectionService:
    """
    Handles LLM-based code correction with smart prompting strategies.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        config_service: ConfigService | None = None,
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.config_service = config_service
        self.code_extractor = CodeExtractor()

    # ID: 4c91c49a-11d4-4dad-acb6-e212ce922653
    async def attempt_correction(
        self,
        file_path: str,
        code: str,
        violations: list[dict[str, Any]],
        module_context: ModuleContext,
        goal: str,
    ) -> dict[str, Any]:
        """
        Attempt to correct code via LLM with appropriate prompting strategy.

        Returns:
            {"status": "success", "code": "..."} or
            {"status": "error", "message": "..."}
        """
        if not all([file_path, code, violations]):
            return {
                "status": "error",
                "message": "Missing required correction context.",
            }

        syntax_only = all(
            v.get("rule", "").startswith(("tooling.", "syntax.")) for v in violations
        )

        violations_json = json.dumps(violations, indent=2)

        try:
            if syntax_only:
                model = PromptModel.load("llm_correction_syntax")
            else:
                model = PromptModel.load("llm_correction_structural")
            llm_client = await self.cognitive.aget_client_for_role(model.manifest.role)

            if syntax_only:
                llm_output = await model.invoke(
                    context={
                        "file_path": file_path,
                        "violations_json": violations_json,
                        "code": code,
                    },
                    client=llm_client,
                    user_id="self_correction",
                )
            else:
                llm_output = await model.invoke(
                    context={
                        "file_path": file_path,
                        "violations_json": violations_json,
                        "code": code.strip(),
                        "module_name": module_context.module_name,
                        "import_path": module_context.import_path,
                        "goal": goal,
                    },
                    client=llm_client,
                    user_id="self_correction",
                )
        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM request failed: {e!s}",
            }

        corrected_code = self._extract_corrected_code(llm_output)

        if not corrected_code:
            return {
                "status": "error",
                "message": "LLM did not produce valid code in any recognized format.",
            }

        validation_result = await validate_code_async(
            file_path, corrected_code, auditor_context=self.auditor
        )

        if validation_result["status"] == "dirty":
            return {
                "status": "correction_failed_validation",
                "message": "The corrected code still fails validation.",
                "violations": validation_result["violations"],
                "code": corrected_code,
            }

        return {
            "status": "success",
            "code": validation_result["code"],
            "message": "Corrected code generated and validated successfully.",
        }

    def _extract_corrected_code(self, llm_output: str) -> str | None:
        """
        Extract code from LLM response using multiple strategies.

        Tries in order:
        1. Write blocks [[write:...]]...[[/write]]
        2. Markdown code fences ```python...```
        3. Raw Python code
        """
        write_blocks = parse_write_blocks(llm_output)
        if write_blocks:
            logger.info("Extracted correction from write block")
            return next(iter(write_blocks.values()))

        code = self.code_extractor.extract(llm_output)
        if code:
            logger.info("Extracted correction from markdown code fence")
            return code

        stripped = llm_output.strip()
        if stripped.startswith(("import ", "from ", "def ", "class ", "@", "#")):
            logger.info("Extracted correction from raw response")
            return stripped

        return None
