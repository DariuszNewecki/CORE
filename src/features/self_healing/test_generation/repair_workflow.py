# src/features/self_healing/test_generation/repair_workflow.py

"""
Coordinates repair attempts for failing test code.
"""

from __future__ import annotations

from typing import Any

from features.self_healing.test_context_analyzer import ModuleContext
from shared.logger import getLogger

from .automatic_repair import AutomaticRepairService
from .llm_correction import LLMCorrectionService
from .test_validator import TestValidator


logger = getLogger(__name__)


# ID: bdc7f4d3-cd46-4a5c-aaf7-49f1e09ed43c
class RepairWorkflow:
    """Manages repair attempts using automatic repairs and LLM correction."""

    def __init__(
        self,
        auto_repair: AutomaticRepairService,
        llm_correction: LLMCorrectionService,
        validator: TestValidator,
        max_attempts: int = 3,
    ):
        self.auto_repair = auto_repair
        self.llm_correction = llm_correction
        self.validator = validator
        self.max_attempts = max_attempts

    # ID: 383cb311-198e-4024-9751-c1e308fe4991
    async def repair_code(
        self,
        test_file: str,
        code: str,
        module_context: ModuleContext,
        goal: str,
    ) -> dict[str, Any]:
        """
        Attempt to repair code through iterative fixing.

        Returns dict with status, code, and optional violations.
        """
        current_code = code
        attempts = 0

        while attempts < self.max_attempts:
            violations = await self.validator.validate_code(
                test_file, current_code, module_context
            )

            if not violations:
                return {"status": "success", "code": current_code}

            logger.info(
                "Validation failed (Attempt %s/%s). Attempting repairs...",
                attempts + 1,
                self.max_attempts,
            )

            # Try automatic repairs first
            repaired_code, repairs = self.auto_repair.apply_all_repairs(current_code)
            if repairs and repaired_code != current_code:
                logger.info("Applied automatic repairs: %s", ", ".join(repairs))
                current_code = repaired_code
                attempts += 1
                continue

            # Log violations before LLM correction
            logger.warning(
                "After auto-repairs, still have %s violations", len(violations)
            )
            for v in violations[:3]:
                logger.warning(
                    "  - %s: %s", v.get("rule", "unknown"), v.get("message", "")[:100]
                )

            # Try LLM correction
            logger.info("Automatic repairs insufficient, calling LLM for correction...")
            correction_result = await self.llm_correction.attempt_correction(
                file_path=test_file,
                code=current_code,
                violations=violations,
                module_context=module_context,
                goal=goal,
            )

            if correction_result["status"] == "success":
                current_code = correction_result["code"]
                # Apply post-correction automatic repairs
                current_code, post_repairs = self.auto_repair.apply_all_repairs(
                    current_code
                )
                if post_repairs:
                    logger.info(
                        "Applied post-correction repairs: %s", ", ".join(post_repairs)
                    )
                attempts += 1
                continue

            # Handle failed LLM correction
            if correction_result["status"] == "correction_failed_validation":
                failed_code = correction_result.get("code")
                if failed_code:
                    repaired, repairs = self.auto_repair.apply_all_repairs(failed_code)
                    if repairs and repaired != failed_code:
                        logger.info(
                            "Auto-repaired failed LLM code: %s", ", ".join(repairs)
                        )
                        current_code = repaired
                        attempts += 1
                        continue

            attempts += 1

        return {
            "status": "failed",
            "code": current_code,
            "violations": violations,
            "message": "Maximum repair attempts reached",
        }
