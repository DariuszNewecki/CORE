# src/features/self_healing/test_generation/llm_correction.py
"""
LLM-based code correction when automatic repairs are insufficient.

This is the "last resort" - only called when deterministic fixes don't work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from body.self_healing.test_context_analyzer import ModuleContext
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parsing import parse_write_blocks
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
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

        # Analyze violations to choose prompting strategy
        syntax_only = all(
            v.get("rule", "").startswith(("tooling.", "syntax.")) for v in violations
        )

        # Build appropriate prompt
        if self.config_service is not None:
            repo_root = Path(await self.config_service.get("REPO_PATH", required=True))
        else:
            repo_root = self.auditor.repo_path

        prompt = self._build_correction_prompt(
            file_path=file_path,
            code=code,
            violations=violations,
            module_context=module_context,
            goal=goal,
            syntax_only=syntax_only,
            repo_root=repo_root,
        )

        # Get LLM response
        try:
            llm_client = await self.cognitive.aget_client_for_role("Coder")
            llm_output = await llm_client.make_request_async(
                prompt, user_id="self_correction"
            )
        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM request failed: {e!s}",
            }

        # Extract corrected code with lenient parsing
        corrected_code = self._extract_corrected_code(llm_output)

        if not corrected_code:
            return {
                "status": "error",
                "message": "LLM did not produce valid code in any recognized format.",
            }

        # Validate the corrected code
        validation_result = await validate_code_async(
            file_path, corrected_code, auditor_context=self.auditor
        )

        if validation_result["status"] == "dirty":
            return {
                "status": "correction_failed_validation",
                "message": "The corrected code still fails validation.",
                "violations": validation_result["violations"],
                "code": corrected_code,  # Return the code so automatic repairs can try
            }

        return {
            "status": "success",
            "code": validation_result["code"],
            "message": "Corrected code generated and validated successfully.",
        }

    def _build_correction_prompt(
        self,
        file_path: str,
        code: str,
        violations: list[dict[str, Any]],
        module_context: ModuleContext,
        goal: str,
        syntax_only: bool,
        repo_root: Path,
    ) -> str:
        """
        Build appropriate correction prompt based on violation type.
        """
        if syntax_only:
            # For syntax errors: be strict about NOT rewriting
            base_prompt = (
                "You are CORE's syntax repair agent.\n\n"
                "The code below has ONLY syntax errors. Your job is to fix the syntax "
                "while preserving ALL logic and structure.\n\n"
                f"File: {file_path}\n\n"
                "SYNTAX ERRORS:\n"
                f"{json.dumps(violations, indent=2)}\n\n"
                "CODE TO FIX:\n"
                f"{code}\n\n"
                "CRITICAL: Fix ONLY the syntax errors listed above. "
                "Do NOT rewrite or restructure the code. "
                "Do NOT add or remove any logic or tests.\n\n"
                "Output the corrected code:"
            )
        else:
            # For structural/logic errors: allow more freedom
            base_prompt = (
                "You are CORE's self-correction agent.\n\n"
                "A recent code generation attempt failed validation.\n"
                "Please analyze the violations and fix the code below.\n\n"
                f"File: {file_path}\n\n"
                "[[violations]]\n"
                f"{json.dumps(violations, indent=2)}\n"
                "[[/violations]]\n\n"
                "[[code]]\n"
                f"{code.strip()}\n"
                "[[/code]]\n\n"
                "Module context:\n"
                f"- Module: {module_context.module_name}\n"
                f"- Import path: {module_context.import_path}\n"
                f"- Goal: {goal}\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Fix ALL violations listed above\n"
                "2. Ensure the code is syntactically valid Python\n"
                "3. Pay special attention to docstring quotes - use MATCHING triple quotes\n"
                "4. NEVER mix quote types in a single docstring\n"
                "5. Output the COMPLETE corrected code\n\n"
                "Provide the corrected code now:"
            )

        # Process through prompt pipeline
        pipeline = PromptPipeline(repo_path=repo_root)
        return pipeline.process(base_prompt)

    def _extract_corrected_code(self, llm_output: str) -> str | None:
        """
        Extract code from LLM response using multiple strategies.

        Tries in order:
        1. Write blocks [[write:...]]...[[/write]]
        2. Markdown code fences ```python...```
        3. Raw Python code
        """
        # Strategy 1: Write blocks
        write_blocks = parse_write_blocks(llm_output)
        if write_blocks:
            logger.info("Extracted correction from write block")
            return next(iter(write_blocks.values()))

        # Strategy 2: Markdown code fences
        code = self.code_extractor.extract(llm_output)
        if code:
            logger.info("Extracted correction from markdown code fence")
            return code

        # Strategy 3: Raw Python
        stripped = llm_output.strip()
        if stripped.startswith(("import ", "from ", "def ", "class ", "@", "#")):
            logger.info("Extracted correction from raw response")
            return stripped

        return None
