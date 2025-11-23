# src/will/agents/self_correction_engine.py
"""
Handles automated correction of code failures by generating and validating LLM-suggested repairs based on structured violation data.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from shared.config import settings
from shared.utils.parsing import parse_write_blocks
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


REPO_PATH = settings.REPO_PATH
pipeline = PromptPipeline(repo_path=REPO_PATH)


async def _attempt_correction(
    failure_context: dict,
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
) -> dict:
    """Attempts to fix a failed validation or test result using an enriched LLM prompt."""
    generator = await cognitive_service.aget_client_for_role("Coder")

    file_path = failure_context.get("file_path")
    code = failure_context.get("code")
    violations = failure_context.get("violations", [])

    if not all([file_path, code, violations]):
        return {
            "status": "error",
            "message": "Missing required failure context fields.",
        }

    correction_prompt = (
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
        "Respond with the full, corrected code in a single write block:\n"
        f"[[write:{file_path}]]\n<corrected code here>\n[[/write]]"
    )

    final_prompt = pipeline.process(correction_prompt)

    # Handle LLM errors defensively so the caller gets a structured error.
    try:
        llm_output = await generator.make_request_async(
            final_prompt,
            user_id="auto_repair",
        )
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"LLM request failed: {str(e)}",
        }

    write_blocks = parse_write_blocks(llm_output)

    if not write_blocks:
        return {
            "status": "error",
            "message": "LLM did not produce a valid correction in a write block.",
        }

    path, fixed_code = list(write_blocks.items())[0]

    validation_result = await validate_code_async(path, fixed_code, auditor_context)
    if validation_result["status"] == "dirty":
        return {
            "status": "correction_failed_validation",
            "message": "The corrected code still fails validation.",
            "violations": validation_result["violations"],
        }

    # Return the validated code directly.
    return {
        "status": "success",
        "code": validation_result["code"],
        "message": "Corrected code generated and validated successfully.",
    }
