# src/will/agents/self_correction_engine.py
"""
Handles automated correction of code failures by generating and validating LLM-suggested repairs based on structured violation data.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from shared.ai.prompt_model import PromptModel
from shared.path_resolver import PathResolver
from shared.utils.parsing import parse_write_blocks
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


def _build_pipeline(path_resolver: PathResolver) -> PromptPipeline:
    return PromptPipeline(repo_path=path_resolver.repo_root)


async def _attempt_correction(
    failure_context: dict,
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    path_resolver: PathResolver,
) -> dict:
    """Attempts to fix a failed validation or test result using an enriched LLM prompt."""
    pipeline = _build_pipeline(path_resolver)
    model = PromptModel.load("self_correction_engine_correction_prompt")
    generator = await cognitive_service.aget_client_for_role(model.manifest.role)

    file_path = failure_context.get("file_path")
    code = failure_context.get("code")
    violations = failure_context.get("violations", [])

    if not all([file_path, code, violations]):
        return {
            "status": "error",
            "message": "Missing required failure context fields.",
        }

    # Handle LLM errors defensively so the caller gets a structured error.
    try:
        llm_output = await model.invoke(
            context={
                "file_path": file_path,
                "violations": json.dumps(violations, indent=2),
                "code": code.strip(),
            },
            client=generator,
            user_id="auto_repair",
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"LLM request failed: {e!s}",
        }

    write_blocks = parse_write_blocks(llm_output)

    if not write_blocks:
        return {
            "status": "error",
            "message": "LLM did not produce a valid correction in a write block.",
        }

    path, fixed_code = next(iter(write_blocks.items()))

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
